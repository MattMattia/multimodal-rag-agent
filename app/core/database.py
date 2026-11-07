from collections.abc import AsyncGenerator
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

# Motor asíncrono de SQLAlchemy conectado mediante asyncpg
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)

# Fábrica de sesiones asíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


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


async def init_db() -> None:
    """Inicializa la base de datos creando extensiones necesarias, tablas ORM e índices vectoriales/léxicos."""
    try:
        async with engine.begin() as conn:
            # Asegurar la extensión pgvector y uuid
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
            # Asegurar que todos los modelos ORM estén cargados en Base.metadata
            import app.models  # noqa: F401
            # Crear tablas faltantes
            await conn.run_sync(Base.metadata.create_all)
            # Migración: asegurar columna embedding si la tabla ya existía
            await conn.execute(
                text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector(768);")
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
        logger.info("Base de datos, tablas e índices vectoriales inicializados exitosamente.")
    except Exception as e:
        logger.warning(
            "No se pudo inicializar la base de datos automáticamente (¿el contenedor aún está iniciando?): %s",
            e,
        )
