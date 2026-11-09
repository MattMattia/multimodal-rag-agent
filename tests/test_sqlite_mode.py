"""S8: dual PostgreSQL / SQLite layer (zero-Docker mode)."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable

from app.core import database
from app.core.config import settings
from app.models.chat import ChatMessage
from app.models.document import Document, DocumentChunk
from app.schemas.search import SearchRequest
from app.services import lexical
from app.services.rag_search import hybrid_search_service

UNREACHABLE_PG = "postgresql+asyncpg://nobody:nopass@127.0.0.1:1/none"
ROOT = Path(__file__).resolve().parents[1]


def _vec(*head: float, size: int = 768):
    return list(head) + [0.0] * (size - len(head))


# --- ORM / engine -----------------------------------------------------------
def test_embedding_column_is_vector_on_postgres_and_json_on_sqlite():
    ddl_pg = str(CreateTable(DocumentChunk.__table__).compile(dialect=postgresql.dialect()))
    ddl_sqlite = str(CreateTable(DocumentChunk.__table__).compile(dialect=sqlite.dialect()))
    assert "embedding VECTOR(768)" in ddl_pg
    assert "embedding JSON" in ddl_sqlite


def test_engine_pool_kwargs_only_for_postgres():
    pg = database.build_engine("postgresql+asyncpg://u:p@localhost:5432/x")
    assert pg.pool.size() == 10 and pg.pool._max_overflow == 20 and pg.pool._recycle == 1800
    lite = database.build_engine("sqlite+aiosqlite:///./never_created.db")  # would raise TypeError with pool_size
    assert lite.dialect.name == "sqlite"
    assert not (ROOT / "never_created.db").exists()


def test_rag_standalone_db_is_gitignored():
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        pytest.skip("Repository hygiene check: .gitignore is not shipped in the API image")
    patterns = gitignore.read_text(encoding="utf-8").splitlines()
    assert "rag_standalone.db" in patterns


# --- init_db ----------------------------------------------------------------
async def test_init_db_on_sqlite_url_creates_schema_without_postgres_ddl(sqlite_db):
    await database.init_db()  # no fallback needed: the configured engine is already SQLite
    assert database.get_active_db_dialect() == "sqlite"
    async with sqlite_db.connect() as conn:
        tables = {r[0] for r in (await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")))}
        indexes = {r[0] for r in (await conn.execute(text("SELECT name FROM sqlite_master WHERE type='index'")))}
    assert {"documents", "document_chunks", "document_images", "chat_messages"} <= tables
    assert "document_chunks_embedding_hnsw_idx" not in indexes


async def test_init_db_adds_message_metadata_to_legacy_sqlite_chat_table(sqlite_db):
    async with sqlite_db.begin() as conn:
        await conn.execute(text("DROP TABLE chat_messages"))
        await conn.execute(
            text("CREATE TABLE chat_messages (id CHAR(32) PRIMARY KEY, session_id CHAR(32) NOT NULL, "
                 "role VARCHAR(20) NOT NULL, content TEXT NOT NULL, citations JSON, executed_tools JSON, "
                 "created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        )
    await database.init_db()
    async with sqlite_db.connect() as conn:
        columns = {r[1] for r in (await conn.execute(text("PRAGMA table_info(chat_messages)")))}
    assert "message_metadata" in columns


async def test_unreachable_postgres_falls_back_to_sqlite(tmp_path, monkeypatch):
    fallback_url = f"sqlite+aiosqlite:///{(tmp_path / 'rag_standalone.db').as_posix()}"
    previous = database.engine
    monkeypatch.setattr(database, "SQLITE_FALLBACK_URL", fallback_url)
    monkeypatch.setattr(settings, "AUTO_FALLBACK_SQLITE", True)
    database.bind_engine(database.build_engine(UNREACHABLE_PG))
    try:
        assert database.get_active_db_dialect() == "postgresql"
        await database.init_db()
        assert database.get_active_db_dialect() == "sqlite"
        assert (tmp_path / "rag_standalone.db").exists()
        async with database.AsyncSessionLocal() as db:  # the session factory was rebound in place
            assert db.get_bind().dialect.name == "sqlite"
            db.add(Document(filename="f.pdf", file_type="pdf", file_path="x", status="completed", doc_metadata={}))
            await db.commit()
            assert len((await db.execute(select(Document))).scalars().all()) == 1
    finally:
        await database.engine.dispose()
        database.bind_engine(previous)


async def test_ddl_error_on_reachable_postgres_propagates_without_sqlite_fallback(monkeypatch):
    """JD-2: only connection-level failures fall back; a DDL error on a live PostgreSQL fails startup loudly."""
    from sqlalchemy.exc import ProgrammingError

    previous = database.engine
    monkeypatch.setattr(settings, "AUTO_FALLBACK_SQLITE", True)
    database.bind_engine(database.build_engine(UNREACHABLE_PG))

    async def _ddl_failure(_target):
        raise ProgrammingError("CREATE INDEX ...", {}, Exception("syntax error at or near hnsw"))

    monkeypatch.setattr(database, "create_schema", _ddl_failure)
    try:
        with pytest.raises(ProgrammingError):
            await database.init_db()
        assert database.get_active_db_dialect() == "postgresql"
    finally:
        await database.engine.dispose()
        database.bind_engine(previous)


async def test_unreachable_postgres_without_fallback_keeps_postgres_engine(monkeypatch):
    previous = database.engine
    monkeypatch.setattr(settings, "AUTO_FALLBACK_SQLITE", False)
    database.bind_engine(database.build_engine(UNREACHABLE_PG))
    try:
        await database.init_db()  # logs a warning, never raises
        assert database.get_active_db_dialect() == "postgresql"
    finally:
        await database.engine.dispose()
        database.bind_engine(previous)


# --- persistence ------------------------------------------------------------
async def test_sqlite_stores_embeddings_and_jsonb_columns_round_trip(sqlite_db):
    doc_id, chunk_id = uuid.uuid4(), uuid.uuid4()
    async with database.AsyncSessionLocal() as db:
        db.add(Document(id=doc_id, filename="d.pdf", file_type="pdf", file_path="x", status="completed",
                        doc_metadata={"k": [1, 2]}))
        await db.flush()
        db.add(DocumentChunk(id=chunk_id, document_id=doc_id, content="hola", chunk_type="text",
                             chunk_metadata={"level": "child"}, embedding=_vec(0.5, 0.25)))
        db.add(ChatMessage(session_id=uuid.uuid4(), role="user", content="hi", message_metadata={"a": 1}))
        await db.commit()
    async with database.AsyncSessionLocal() as db:
        chunk = (await db.execute(select(DocumentChunk))).scalar_one()
        assert chunk.id == chunk_id and chunk.embedding[:2] == [0.5, 0.25] and len(chunk.embedding) == 768
        assert chunk.chunk_metadata == {"level": "child"}


# --- retrieval --------------------------------------------------------------
async def _seed_chunks(rows):
    """rows: (filename, content, embedding|None). Returns {content: chunk_id}."""
    ids = {}
    async with database.AsyncSessionLocal() as db:
        docs = {}
        for filename, _, _ in rows:
            if filename not in docs:
                docs[filename] = uuid.uuid4()
                db.add(Document(id=docs[filename], filename=filename, file_type="pdf", file_path=filename,
                                status="completed", doc_metadata={}))
        await db.flush()
        for filename, content, embedding in rows:
            cid = uuid.uuid4()
            ids[content] = cid
            db.add(DocumentChunk(id=cid, document_id=docs[filename], content=content, chunk_type="text",
                                 chunk_metadata={}, embedding=embedding))
        await db.commit()
    return ids


async def test_sqlite_dense_retrieval_ranks_by_exact_cosine_over_embedded_chunks(sqlite_db):
    ids = await _seed_chunks([
        ("a.pdf", "cerca", _vec(1.0, 0.1)),
        ("a.pdf", "ortogonal", _vec(0.0, 1.0)),
        ("a.pdf", "opuesto", _vec(-1.0, 0.0)),
        ("a.pdf", "padre sin embedding", None),
    ])
    async with database.AsyncSessionLocal() as db:
        items = await hybrid_search_service._dense_retrieval_sqlite(
            db=db, query_vector=_vec(1.0, 0.0), limit=10, filter_document_id=None
        )
    assert [i["chunk_id"] for i in items] == [ids["cerca"], ids["ortogonal"], ids["opuesto"]]
    assert items[0]["score"] == pytest.approx(1.0 / (1.0 + 0.01) ** 0.5, abs=1e-4)
    assert items[1]["score"] == 0.0 and items[2]["score"] == 0.0  # similarity is clamped to [0, 1]


async def test_sqlite_sparse_retrieval_is_bilingual_and_accent_insensitive(sqlite_db):
    ids = await _seed_chunks([
        ("fin.pdf", "Los ingresos de Norteamérica fueron de 45 millones", None),
        ("fin.pdf", "Quarterly revenue grew in the European market", None),
        ("sec.pdf", "Controles de sanitización de archivos subidos", None),
    ])
    async with database.AsyncSessionLocal() as db:
        run = lambda q: hybrid_search_service._sparse_retrieval_sqlite(  # noqa: E731
            db=db, query_text=q, limit=10, filter_document_id=None
        )
        es = await run("ingresos norteamerica")
        en = await run("revenue growth")
        accents = await run("sanitizacion")
        none = await run("zzzzqqq")
    assert [i["chunk_id"] for i in es] == [ids["Los ingresos de Norteamérica fueron de 45 millones"]]
    assert [i["chunk_id"] for i in en] == [ids["Quarterly revenue grew in the European market"]]
    assert [i["chunk_id"] for i in accents] == [ids["Controles de sanitización de archivos subidos"]]
    assert none == []


async def test_sqlite_search_runs_the_full_pipeline_and_respects_document_filter(sqlite_db):
    ids = await _seed_chunks([
        ("a.pdf", "presupuesto anual de infraestructura cloud", _vec(1.0)),
        ("b.pdf", "presupuesto del equipo de seguridad", _vec(0.0, 1.0)),
    ])
    request = SearchRequest(query="presupuesto", top_k=5, mode="hybrid", rerank=False, include_parent=False)
    async with database.AsyncSessionLocal() as db:
        response = await hybrid_search_service.search(db=db, request=request)
        assert {r.chunk_id for r in response.results} == set(ids.values())
        assert response.diagnostics.db_dialect == "sqlite"
        doc_a = (await db.execute(select(Document.id).where(Document.filename == "a.pdf"))).scalar_one()
        filtered = await hybrid_search_service.search(
            db=db, request=request.model_copy(update={"filter_document_id": doc_a})
        )
    assert [r.document_name for r in filtered.results] == ["a.pdf"]


# --- lexical helpers --------------------------------------------------------
def test_tokenize_is_bilingual_lowercase_accentless_and_drops_stopwords():
    tokens = lexical.tokenize("Los INGRESOS de Norteamérica, the revenue & EBITDA 34%")
    for stopword in ("los", "de", "the", "&"):
        assert stopword not in tokens
    assert "34" in tokens and len(tokens) == 5
    # accent folding, case folding and light plural stemming in both languages
    assert lexical.tokenize("Norteamérica") == lexical.tokenize("norteamerica")
    assert lexical.tokenize("ingresos") == lexical.tokenize("INGRESO")
    assert lexical.tokenize("controles") == lexical.tokenize("control")
    assert lexical.tokenize("revenues") == lexical.tokenize("revenue")
    assert lexical.tokenize("sanitización") == lexical.tokenize("sanitizaciones")
    assert lexical.tokenize("") == [] and lexical.tokenize("   ") == []


def test_bm25_scores_rank_rare_matching_terms_first_and_zero_for_no_match():
    docs = [lexical.tokenize(t) for t in ("hnsw index m16 build", "index of the table", "completely unrelated words")]
    scores = lexical.bm25_scores(lexical.tokenize("hnsw index"), docs)
    assert scores[0] > scores[1] > 0.0
    assert scores[2] == 0.0
    assert lexical.bm25_scores([], docs) == [0.0, 0.0, 0.0]
    assert lexical.bm25_scores(["x"], []) == []
