"""Phase 3 (PERF-01..PERF-05): async concurrency, database and RAG pipeline tests.

No network, no Langfuse and no real Gemini: every external collaborator is mocked.
"""
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image
from sqlalchemy.dialects import postgresql

from app.core import database
from app.models.chat import ChatMessage
from app.models.document import DocumentChunk
from app.schemas.search import SearchRequest
from app.services import ingestion as ingestion_module
from app.services.agent import AutonomousAgentService
from app.services.ingestion import IngestionService
from app.services.rag_search import HybridSearchService
from app.services.vision import VisionService


@pytest.fixture
def no_langfuse():
    """Keep telemetry inert so unit tests never reach the Langfuse server."""
    from app.core.telemetry import telemetry_service

    with patch.object(telemetry_service, "_enabled", False):
        yield


# ---------------------------------------------------------------------------
# PERF-01: blocking work runs off the event loop
# ---------------------------------------------------------------------------
def _thread_recording_pdf(threads: list[int]):
    def fake_pdf(title, summary, key_points=None, sections=None):
        threads.append(threading.get_ident())
        return {"status": "success", "download_url": "/uploads/reports/x.pdf", "file_path": "x.pdf", "filename": "x.pdf"}

    return fake_pdf


async def test_dispatch_tool_call_generates_pdf_in_a_worker_thread():
    threads: list[int] = []
    service = AutonomousAgentService()
    with patch("app.services.agent.execute_generate_report_pdf", _thread_recording_pdf(threads)):
        result, citations = await service._dispatch_tool_call(
            db=MagicMock(),
            tool_name="generate_report_pdf",
            tool_args={"title": "T", "summary": "S", "key_points": ["a"]},
        )
    assert result["status"] == "success"
    assert citations == []
    assert len(threads) == 1
    assert threads[0] != threading.get_ident()


async def test_fallback_turn_generates_pdf_in_a_worker_thread(no_langfuse):
    threads: list[int] = []
    service = AutonomousAgentService()
    with patch("app.services.agent.execute_generate_report_pdf", _thread_recording_pdf(threads)):
        response = await service._execute_fallback_turn(
            db=MagicMock(), user_message="genera un pdf", session_id=uuid.uuid4(), prior_messages=[]
        )
    assert [t.tool_name for t in response.executed_tools] == ["generate_report_pdf"]
    assert response.executed_tools[0].tool_output["status"] == "success"
    assert len(threads) == 1
    assert threads[0] != threading.get_ident()


class _FakeCropped:
    def to_image(self, resolution):
        assert resolution == 150
        return SimpleNamespace(save=lambda path, format: Path(path).write_bytes(b"png"))


class _FakePage:
    width = 600
    height = 800
    images = [{"x0": 0, "top": 0, "x1": 200, "bottom": 200}]

    def __init__(self, text: str):
        self._text = text

    def extract_tables(self):
        return [[["h1", "h2"], ["a", "b"]]]

    def crop(self, bbox):
        return _FakeCropped()

    def extract_text(self):
        return self._text


class _FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeSession:
    """Records flush/commit calls and serves the two selects the pipeline performs."""

    def __init__(self, doc):
        self.doc = doc
        self.added: list[Any] = []
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0
        self.events: list[str] = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1
        self.events.append("flush")

    async def commit(self):
        self.commits += 1
        self.events.append("commit")

    async def rollback(self):
        self.rollbacks += 1

    async def execute(self, stmt):
        result = MagicMock()
        result.scalar_one_or_none.return_value = self.doc
        chunks = [o for o in self.added if isinstance(o, DocumentChunk)]
        result.scalars.return_value.all.return_value = chunks
        return result

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def test_pdf_ingestion_runs_pdfplumber_in_thread_with_one_flush_and_one_final_commit(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"%PDF-1.4")
    doc = SimpleNamespace(
        id=uuid.uuid4(),
        file_path=str(pdf_file),
        file_type="application/pdf",
        filename="doc.pdf",
        status="pending",
        error_message=None,
        doc_metadata={},
    )
    session = _FakeSession(doc)
    open_threads: list[int] = []
    long_text = "Frase de prueba para dividir en varios fragmentos. " * 60

    def fake_open(path):
        open_threads.append(threading.get_ident())
        return _FakePdf([_FakePage(long_text), _FakePage(long_text)])

    service = IngestionService()
    monkeypatch.setattr(ingestion_module, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(ingestion_module.pdfplumber, "open", fake_open)
    describe = AsyncMock(return_value="descripcion")
    monkeypatch.setattr(ingestion_module.vision_service, "describe_image", describe)
    embed_threads: list[int] = []

    async def fake_embed(texts, batch_size=50):
        session.events.append("embed")
        embed_threads.append(threading.get_ident())
        return [[0.0] * 768 for _ in texts]

    monkeypatch.setattr(ingestion_module.embedding_service, "get_embeddings_batch", fake_embed)

    await service.process_document_pipeline(doc.id)

    # pdfplumber ran in a worker thread; Gemini Vision + embeddings stayed on the loop thread
    assert len(open_threads) == 1
    assert open_threads[0] != threading.get_ident()
    assert describe.await_count == 2
    assert embed_threads == [threading.get_ident()]

    # Result is correct
    assert doc.status == "completed"
    assert doc.doc_metadata["total_pages"] == 2
    assert doc.doc_metadata["total_tables"] == 2
    assert doc.doc_metadata["total_images"] == 2
    chunks = [o for o in session.added if isinstance(o, DocumentChunk)]
    assert doc.doc_metadata["total_chunks"] == len(chunks)
    assert {c.chunk_type for c in chunks} >= {"table", "image_description", "text"}
    # R2-BUG-04: only leaf chunks are embedded; parents that have children keep embedding=None
    parents_with_children = {c.parent_id for c in chunks if c.parent_id is not None}
    for c in chunks:
        assert (c.embedding is None) == (c.id in parents_with_children)

    # Children link to pre-generated parent ids and parents precede their children
    ids = {c.id for c in chunks if c.id is not None}
    children = [c for c in chunks if c.parent_id is not None]
    assert children, "expected child chunks"
    order = {id(c): i for i, c in enumerate(chunks)}
    by_id = {c.id: c for c in chunks if c.id is not None}
    for child in children:
        assert child.parent_id in ids
        assert order[id(by_id[child.parent_id])] < order[id(child)]

    # Exactly one flush (before embeddings) and exactly one commit after the "processing" commit
    assert session.flushes == 1
    assert session.events.index("flush") < session.events.index("embed")
    assert session.commits == 2  # "processing" status commit + single final commit
    assert session.events[-1] == "commit"
    assert session.events.count("commit") == 2
    assert session.events[:1] == ["commit"]


async def test_ingestion_failure_still_marks_document_failed(tmp_path, monkeypatch):
    doc = SimpleNamespace(
        id=uuid.uuid4(),
        file_path=str(tmp_path / "missing.pdf"),
        file_type="application/pdf",
        filename="missing.pdf",
        status="pending",
        error_message=None,
        doc_metadata={},
    )
    session = _FakeSession(doc)
    monkeypatch.setattr(ingestion_module, "AsyncSessionLocal", lambda: session)

    await IngestionService().process_document_pipeline(doc.id)

    assert session.rollbacks == 1
    assert session.commits == 2  # "processing" + failed-status update


# ---------------------------------------------------------------------------
# PERF-02: VisionService
# ---------------------------------------------------------------------------
def _ready_vision(client) -> VisionService:
    service = VisionService()
    service._client = client
    service._initialized = True
    service._ensure_client = lambda: None  # type: ignore[method-assign]
    return service


def _png(path: Path) -> Path:
    Image.new("RGB", (8, 8), "red").save(path, format="PNG")
    return path


async def test_describe_image_releases_the_file_handle(tmp_path):
    image_path = _png(tmp_path / "pic.png")
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(return_value=SimpleNamespace(text=" una imagen "))
    service = _ready_vision(client)

    description = await service.describe_image(str(image_path))

    assert description == "una imagen"
    image_path.unlink()  # raises PermissionError on Windows if the handle leaked
    assert not image_path.exists()


async def test_describe_image_caches_working_model(tmp_path):
    image_path = _png(tmp_path / "pic.png")
    calls: list[str] = []

    async def fake_generate(model, contents):
        calls.append(model)
        if len(calls) == 1:
            raise RuntimeError("404 NOT_FOUND")
        return SimpleNamespace(text="ok")

    client = MagicMock()
    client.aio.models.generate_content = fake_generate
    service = _ready_vision(client)

    assert await service.describe_image(str(image_path)) == "ok"
    assert await service.describe_image(str(image_path)) == "ok"

    assert len(calls) == 3
    assert calls[1] == calls[2] != calls[0]
    assert service._working_model == calls[1]


def test_vision_module_no_longer_depends_on_legacy_sdk():
    import app.services.vision as vision_module

    source = Path(vision_module.__file__).read_text(encoding="utf-8")
    assert "google.generativeai" not in source
    assert not hasattr(VisionService(), "_legacy_model")


# ---------------------------------------------------------------------------
# PERF-03: GIN/HNSW DDL and websearch_to_tsquery
# ---------------------------------------------------------------------------
async def test_init_db_issues_english_gin_and_tuned_hnsw_indexes():
    statements: list[str] = []
    conn = MagicMock()

    async def fake_execute(stmt, *args, **kwargs):
        statements.append(str(stmt))

    conn.execute = fake_execute
    conn.run_sync = AsyncMock()
    begin = MagicMock()
    begin.__aenter__ = AsyncMock(return_value=conn)
    begin.__aexit__ = AsyncMock(return_value=False)

    fake_engine = MagicMock()
    fake_engine.begin.return_value = begin
    with patch.object(database, "engine", fake_engine):
        await database.init_db()

    ddl = " ".join(" ".join(s.split()) for s in statements)
    assert (
        "CREATE INDEX IF NOT EXISTS document_chunks_content_tsv_en_idx "
        "ON document_chunks USING gin (to_tsvector('english', content));"
    ) in ddl
    assert "hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);" in ddl
    # the Spanish index is kept
    assert "document_chunks_content_tsv_idx" in ddl
    assert "to_tsvector('spanish', content)" in ddl


async def test_sparse_retrieval_uses_websearch_tsquery_matching_index_expressions():
    captured = []
    db = MagicMock()
    empty = MagicMock()
    empty.all.return_value = []

    async def fake_execute(stmt):
        captured.append(stmt)
        return empty

    db.execute = fake_execute

    await HybridSearchService()._sparse_retrieval(
        db=db, query_text="como configuro la base?", limit=5, filter_document_id=None
    )

    sql = str(
        captured[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "websearch_to_tsquery('spanish'" in sql
    assert "websearch_to_tsquery('english'" in sql
    assert "plainto_tsquery" not in sql
    # Expression must match the index definitions exactly for the GIN indexes to be usable
    assert "to_tsvector('spanish', document_chunks.content)" in sql
    assert "to_tsvector('english', document_chunks.content)" in sql


# ---------------------------------------------------------------------------
# PERF-04: parent-child dedup in hybrid search
# ---------------------------------------------------------------------------
def _candidate(chunk_id, parent_id=None, score=0.5, name="doc.pdf"):
    return {
        "chunk_id": chunk_id,
        "document_id": uuid.UUID(int=1),
        "document_name": name,
        "content": f"content {chunk_id}",
        "parent_id": parent_id,
        "chunk_type": "text",
        "page_number": 1,
        "score": score,
        "metadata": {},
    }


async def test_hybrid_search_returns_one_result_per_parent_block():
    parent, child_a, child_b, other = (uuid.uuid4() for _ in range(4))
    dense = [
        _candidate(child_a, parent),  # best-scoring member of the parent block
        _candidate(parent),
        _candidate(child_b, parent),
        _candidate(other),
    ]
    seen_by_reranker: list[Any] = []

    async def fake_rerank(query, candidates, top_n):
        seen_by_reranker.extend(candidates)
        return candidates[:top_n]

    service = HybridSearchService()
    request = SearchRequest(query="algo", top_k=5, include_parent=False)
    with patch("app.services.rag_search.embedding_service.get_embedding", AsyncMock(return_value=[0.0])), \
         patch.object(service, "_dense_retrieval", AsyncMock(return_value=dense)), \
         patch.object(service, "_sparse_retrieval", AsyncMock(return_value=[])), \
         patch("app.services.rag_search.reranker_service.rerank", fake_rerank):
        response = await service.search(db=MagicMock(), request=request)

    block_ids = [(r.parent_id or r.chunk_id) for r in response.results]
    assert block_ids == [parent, other]
    assert [r.chunk_id for r in response.results] == [child_a, other]  # best-scoring kept
    assert [r.rank for r in response.results] == [1, 2]
    assert response.total_results == 2
    # deduplicated before reranking
    assert [(c["parent_id"] or c["chunk_id"]) for c in seen_by_reranker] == [parent, other]


async def test_hybrid_search_dedup_applies_without_reranker():
    parent, child_a, child_b = (uuid.uuid4() for _ in range(3))
    dense = [_candidate(child_a, parent), _candidate(child_b, parent), _candidate(parent)]
    service = HybridSearchService()
    request = SearchRequest(query="algo", top_k=3, include_parent=False, rerank=False)
    with patch("app.services.rag_search.embedding_service.get_embedding", AsyncMock(return_value=[0.0])), \
         patch.object(service, "_dense_retrieval", AsyncMock(return_value=dense)), \
         patch.object(service, "_sparse_retrieval", AsyncMock(return_value=[])):
        response = await service.search(db=MagicMock(), request=request)

    assert [r.chunk_id for r in response.results] == [child_a]


# ---------------------------------------------------------------------------
# PERF-05: pool configuration, get_db and history window
# ---------------------------------------------------------------------------
@pytest.mark.postgres_only
def test_engine_pool_is_tuned():
    pool = database.engine.pool
    assert pool.size() == 10
    assert pool._max_overflow == 20
    assert pool._recycle == 1800
    assert pool._pre_ping is True


async def test_get_db_does_not_close_session_redundantly():
    session = MagicMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)

    with patch.object(database, "AsyncSessionLocal", return_value=cm):
        gen = database.get_db()
        assert await gen.__anext__() is session
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()
        session.close.assert_not_awaited()
        cm.__aexit__.assert_awaited_once()

        gen = database.get_db()
        await gen.__anext__()
        with pytest.raises(ValueError):
            await gen.athrow(ValueError("boom"))
        session.rollback.assert_awaited_once()


def _history(n: int) -> list[ChatMessage]:
    return [
        ChatMessage(
            session_id=uuid.uuid4(),
            role="user" if i % 2 == 0 else "assistant",
            content=f"msg-{i}",
            citations=[],
            executed_tools=[],
        )
        for i in range(n)
    ]


def _service_capturing_contents(captured: list[list[Any]]) -> AutonomousAgentService:
    service = AutonomousAgentService()
    service._client = object()
    service._ensure_client = lambda: True  # type: ignore[method-assign]

    async def fake_call(contents, config, preferred_model=None):
        captured.append(list(contents))
        return SimpleNamespace(function_calls=None, candidates=[], text="ok", usage_metadata=None), "m"

    service._call_gemini_with_fallback = fake_call  # type: ignore[method-assign]
    return service


def _texts(contents) -> list[str]:
    return [c.parts[0].text for c in contents]


def _fake_db_with_history(history: list[ChatMessage]) -> MagicMock:
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = history
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


async def test_sync_turn_sends_only_last_20_prior_messages_to_gemini(no_langfuse):
    captured: list[list[Any]] = []
    service = _service_capturing_contents(captured)
    history = _history(30)

    await service._execute_gemini_turn(
        db=MagicMock(), user_message="nuevo", session_id=uuid.uuid4(), prior_messages=history
    )

    assert _texts(captured[0]) == [f"msg-{i}" for i in range(10, 30)] + ["nuevo"]


async def test_execute_turn_loads_full_history_but_sends_last_20(no_langfuse):
    captured: list[list[Any]] = []
    service = _service_capturing_contents(captured)
    history = _history(30)
    db = _fake_db_with_history(history)

    await service.execute_turn(db=db, user_message="nuevo", session_id=uuid.uuid4())

    assert len(captured[0]) == 21
    assert _texts(captured[0])[0] == "msg-10"
    assert _texts(captured[0])[-1] == "nuevo"
    assert len(history) == 30  # nothing truncated in storage


async def test_stream_turn_sends_only_last_20_prior_messages_to_gemini(no_langfuse):
    captured: list[list[Any]] = []
    service = _service_capturing_contents(captured)
    db = _fake_db_with_history(_history(30))

    events = [e async for e in service.execute_turn_stream(db=db, user_message="nuevo")]

    assert events
    assert _texts(captured[0]) == [f"msg-{i}" for i in range(10, 30)] + ["nuevo"]
