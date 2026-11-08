import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

# Base de datos local de respaldo (modo Zero-Docker) cuando PostgreSQL no responde
SQLITE_FALLBACK_URL = "sqlite+aiosqlite:///./rag_standalone.db"
POSTGRES_CONNECT_TIMEOUT_SECONDS = 10


def _is_postgres_url(url: str) -> bool:
    return url.startswith("postgresql")


def build_engine(url: str) -> AsyncEngine:
    """Crea un motor asíncrono ajustado al dialecto: el pool solo se configura para PostgreSQL.

    `sqlite+aiosqlite` lanza TypeError si recibe `pool_size`/`max_overflow`.
    """
    kwargs: dict[str, Any] = {"echo": settings.DEBUG, "future": True, "pool_pre_ping": True}
    if _is_postgres_url(url):
        kwargs.update(
            pool_size=10,
            max_overflow=20,
            pool_recycle=1800,
            connect_args={"timeout": POSTGRES_CONNECT_TIMEOUT_SECONDS},
        )
    else:
        kwargs["connect_args"] = {"timeout": 30}
    new_engine = create_async_engine(url, **kwargs)
    if new_engine.dialect.name == "sqlite":
        @event.listens_for(new_engine.sync_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _record):  # pragma: no cover - trivial pragma
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return new_engine


# Motor asíncrono de SQLAlchemy (asyncpg para PostgreSQL, aiosqlite para SQLite)
engine = build_engine(settings.DATABASE_URL)

# Fábrica de sesiones asíncronas. Los módulos la importan por valor, así que un cambio de motor
# se aplica reconfigurándola en el lugar (`bind_engine`) y nunca reemplazando el objeto.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def bind_engine(new_engine: AsyncEngine) -> None:
    """Activa `new_engine` como motor de la aplicación y re-vincula `AsyncSessionLocal` en el lugar."""
    global engine
    engine = new_engine
    AsyncSessionLocal.configure(bind=new_engine)


def get_active_db_dialect() -> str:
    """Dialecto de la base de datos activa: "postgresql" o "sqlite"."""
    return "sqlite" if engine.dialect.name == "sqlite" else "postgresql"


class Base(DeclarativeBase):
    """Clase base declarativa para todos los modelos ORM de la aplicación."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Inyección de dependencias para obtener una sesión asíncrona de base de datos en endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def _ensure_message_metadata_column(conn: AsyncConnection, dialect: str) -> None:
    """Migración idempotente: añade `chat_messages.message_metadata` si la tabla ya existía sin ella."""
    if dialect == "sqlite":
        rows = await conn.execute(text("PRAGMA table_info(chat_messages)"))
        if "message_metadata" not in {row[1] for row in rows}:
            await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN message_metadata JSON"))
        return
    await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS message_metadata JSONB;"))


async def create_schema(target: AsyncEngine) -> None:
    """Crea tablas e índices según el dialecto de `target` (extensiones, HNSW y GIN solo en PostgreSQL)."""
    # Asegurar que todos los modelos ORM estén cargados en Base.metadata
    import app.models  # noqa: F401

    dialect = "sqlite" if target.dialect.name == "sqlite" else "postgresql"
    async with target.begin() as conn:
        if dialect == "postgresql":
            # Asegurar la extensión pgvector y uuid
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        # Crear tablas faltantes
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_message_metadata_column(conn, dialect)
        if dialect == "sqlite":
            return
        # Migración: asegurar columna embedding si la tabla ya existía
        await conn.execute(
            text(
                f"ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector({settings.EMBEDDING_DIMENSION});"
            )
        )
        # Índice HNSW para búsqueda por similitud de coseno
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS document_chunks_embedding_hnsw_idx "
                "ON document_chunks USING hnsw (embedding vector_cosine_ops) "
                "WITH (m = 16, ef_construction = 64);"
            )
        )
        # Índice GIN para búsqueda léxica full-text search en español
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS document_chunks_content_tsv_idx "
                "ON document_chunks USING gin (to_tsvector('spanish', content));"
            )
        )
        # Índice GIN para búsqueda léxica full-text search en inglés
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS document_chunks_content_tsv_en_idx "
                "ON document_chunks USING gin (to_tsvector('english', content));"
            )
        )


async def _auto_seed_if_empty() -> None:
    """Siembra el Golden Corpus cuando `documents` está vacía (el proyecto jamás arranca vacío)."""
    if not settings.AUTO_SEED_DEMO_CORPUS:
        return
    try:
        from app.services.demo_seeder import seed_demo_corpus_if_empty

        await seed_demo_corpus_if_empty()
    except Exception as e:  # una siembra fallida nunca debe impedir el arranque
        logger.warning("No se pudo sembrar el Golden Corpus automáticamente: %s", e)


def _is_connection_error(exc: BaseException) -> bool:
    """True si el fallo (o cualquier causa encadenada) es de conectividad: servidor inalcanzable o arrancando.

    Errores de autenticación, catálogo inexistente o DDL indican mala configuración y no califican.
    """
    try:
        from asyncpg.exceptions import CannotConnectNowError
    except ImportError:  # pragma: no cover - asyncpg siempre está instalado con PostgreSQL
        CannotConnectNowError = ()  # type: ignore[assignment,misc]

    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (OSError, TimeoutError, CannotConnectNowError)):
            return True
        current = getattr(current, "orig", None) or current.__cause__ or current.__context__
    return False


async def init_db() -> None:
    """Inicializa la base de datos (extensiones, tablas ORM, índices) y, si PostgreSQL no responde,
    continúa sobre SQLite cuando `AUTO_FALLBACK_SQLITE` está activo. Luego auto-siembra el Golden Corpus.

    Un error que no sea de conectividad (p. ej. DDL fallido) sobre PostgreSQL se propaga y detiene el arranque.
    """
    try:
        await create_schema(engine)
        logger.info("Base de datos [%s], tablas e índices inicializados exitosamente.", get_active_db_dialect())
    except Exception as e:
        if engine.dialect.name != "sqlite" and not _is_connection_error(e):
            raise
        if engine.dialect.name == "sqlite" or not settings.AUTO_FALLBACK_SQLITE:
            logger.warning(
                "No se pudo inicializar la base de datos automáticamente (¿el contenedor aún está iniciando?): %s",
                e,
            )
            return
        logger.warning(
            "PostgreSQL no disponible (%s). Cambiando a SQLite local (%s): sin pgvector, búsqueda exacta en Python.",
            e,
            SQLITE_FALLBACK_URL,
        )
        unreachable = engine
        bind_engine(build_engine(SQLITE_FALLBACK_URL))
        await unreachable.dispose()
        try:
            await create_schema(engine)
        except Exception as sqlite_err:
            logger.warning("No se pudo inicializar el esquema SQLite de respaldo: %s", sqlite_err)
            return
    await _auto_seed_if_empty()
