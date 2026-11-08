"""S11: SearchDiagnostics in search responses and in the agent SSE events."""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import database
from app.core.telemetry import telemetry_service
from app.main import app
from app.models.document import Document, DocumentChunk
from app.schemas.search import SearchDiagnostics, SearchRequest
from app.services.agent import AutonomousAgentService
from app.services.rag_search import hybrid_search_service

FIELDS = {
    "db_dialect", "embedding_ms", "dense_ms", "sparse_ms", "rrf_fusion_ms",
    "rerank_ms", "total_ms", "raw_candidates_count", "deduped_blocks_count",
}


@pytest.fixture
def http():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def no_langfuse():
    with patch.object(telemetry_service, "_enabled", False):
        yield


def _candidate(name="d.pdf", parent=None):
    return {
        "chunk_id": uuid.uuid4(), "document_id": uuid.uuid4(), "document_name": name, "content": "contenido",
        "parent_id": parent, "chunk_type": "text", "page_number": 1, "score": 0.5, "metadata": {},
    }


def test_search_diagnostics_schema_has_exactly_the_documented_fields():
    assert set(SearchDiagnostics.model_fields) == FIELDS


async def test_search_measures_every_stage_with_perf_counter(monkeypatch):
    shared_parent = uuid.uuid4()
    c1, c2, c3 = _candidate(parent=shared_parent), _candidate(parent=shared_parent), _candidate()
    dense, sparse = [c1, c3], [c1, c2]
    monkeypatch.setattr(hybrid_search_service, "_dense_retrieval", AsyncMock(return_value=dense))
    monkeypatch.setattr(hybrid_search_service, "_sparse_retrieval", AsyncMock(return_value=sparse))
    monkeypatch.setattr("app.services.rag_search.embedding_service.get_embedding", AsyncMock(return_value=[0.0]))

    clock = iter(range(0, 1000))  # every perf_counter() call advances 1 second -> deterministic stage times
    monkeypatch.setattr("app.services.rag_search.time", SimpleNamespace(perf_counter=lambda: next(clock)))
    request = SearchRequest(query="hola", top_k=5, mode="hybrid", rerank=False, include_parent=False)

    response = await hybrid_search_service.search(db=MagicMock(), request=request)

    diag = response.diagnostics
    assert set(diag.model_dump()) == FIELDS
    assert diag.db_dialect in ("postgresql", "sqlite")
    for stage in ("embedding_ms", "dense_ms", "sparse_ms", "rrf_fusion_ms"):
        assert getattr(diag, stage) == 1000.0  # exactly one tick between the stage's two perf_counter() calls
    assert diag.rerank_ms == 0.0  # rerank disabled
    assert diag.total_ms > diag.embedding_ms
    assert diag.raw_candidates_count == 3  # c1 appears in both lists
    assert diag.deduped_blocks_count == 2  # c1 and c2 share a parent block


async def test_sparse_mode_reports_zero_for_stages_that_did_not_run(monkeypatch):
    monkeypatch.setattr(hybrid_search_service, "_sparse_retrieval", AsyncMock(return_value=[_candidate()]))
    dense = AsyncMock()
    monkeypatch.setattr(hybrid_search_service, "_dense_retrieval", dense)
    request = SearchRequest(query="hola", top_k=3, mode="sparse", rerank=False, include_parent=False)
    diag = (await hybrid_search_service.search(db=MagicMock(), request=request)).diagnostics
    assert dense.await_count == 0
    assert diag.embedding_ms == 0.0 and diag.dense_ms == 0.0
    assert diag.raw_candidates_count == 1 and diag.deduped_blocks_count == 1


async def test_search_endpoint_returns_diagnostics(http, sqlite_db):
    doc_id = uuid.uuid4()
    async with database.AsyncSessionLocal() as db:
        db.add(Document(id=doc_id, filename="d.pdf", file_type="pdf", file_path="x", status="completed",
                        doc_metadata={}))
        await db.flush()
        db.add(DocumentChunk(document_id=doc_id, content="ingresos trimestrales", chunk_type="text",
                             chunk_metadata={}, embedding=[0.1] * 768))
        await db.commit()
    async with http as client:
        resp = await client.post("/api/v1/search", json={"query": "ingresos", "mode": "sparse"})
    assert resp.status_code == 200
    diag = resp.json()["diagnostics"]
    assert set(diag) == FIELDS and diag["db_dialect"] == "sqlite"
    assert diag["total_ms"] >= 0 and diag["raw_candidates_count"] == 1


# --- agent SSE ----------------------------------------------------------------
def _events(raw):
    return [json.loads(e[len("data: "):]) for e in raw]


def _fake_db():
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


DIAG = {
    "db_dialect": "sqlite", "embedding_ms": 1.0, "dense_ms": 2.0, "sparse_ms": 3.0, "rrf_fusion_ms": 0.5,
    "rerank_ms": 4.0, "total_ms": 10.5, "raw_candidates_count": 6, "deduped_blocks_count": 4,
}


async def test_fallback_stream_emits_tool_end_and_metadata_with_diagnostics():
    service = AutonomousAgentService()
    service._ensure_client = lambda: False
    search = AsyncMock(return_value={
        "context_text": "ctx", "citations": [], "total_found": 1, "diagnostics": DIAG,
    })
    with patch("app.services.agent.execute_search_knowledge_base", search):
        raw = [e async for e in service.execute_turn_stream(db=_fake_db(), user_message="quien es mattia")]
    events = _events(raw)
    types = [e["type"] for e in events]
    assert types[-1] == "metadata" and "tool_end" in types and "token" in types
    tool_end = next(e for e in events if e["type"] == "tool_end")
    assert tool_end["tool_name"] == "search_knowledge_base"
    assert tool_end["diagnostics"] == DIAG and tool_end["duration_ms"] >= 0
    metadata = events[-1]
    assert metadata["diagnostics"] == DIAG and metadata["duration_ms"] >= 0
    # existing metadata fields are untouched
    assert {"citations", "executed_tools", "session_id"} <= set(metadata)


async def test_gemini_stream_emits_tool_end_per_tool_and_metadata_diagnostics():
    service = AutonomousAgentService()
    service._client = object()
    service._ensure_client = lambda: True
    from google.genai import types as gt

    content = gt.Content(role="model", parts=[gt.Part.from_text(text="call")])
    call_response = SimpleNamespace(
        function_calls=[SimpleNamespace(name="search_knowledge_base", args={"query": "cv"})],
        candidates=[SimpleNamespace(content=content)], text=None, usage_metadata=None,
    )
    final = SimpleNamespace(function_calls=None, candidates=[], text="listo", usage_metadata=None)
    service._call_gemini_with_fallback = AsyncMock(side_effect=[(call_response, "m"), (final, "m")])

    async def dispatch(db, tool_name, tool_args, options=None, tool_meta=None):
        tool_meta["diagnostics"] = DIAG
        return "ctx", []

    service._dispatch_tool_call = dispatch
    events = _events([e async for e in service.execute_turn_stream(db=_fake_db(), user_message="hola")])
    ends = [e for e in events if e["type"] == "tool_end"]
    assert len(ends) == 1 and ends[0]["diagnostics"] == DIAG and ends[0]["tool_name"] == "search_knowledge_base"
    assert events[-1]["type"] == "metadata" and events[-1]["diagnostics"] == DIAG
    assert events[-1]["duration_ms"] >= 0
    # the tool_end event is emitted before the final answer tokens
    assert [e["type"] for e in events].index("tool_end") < [e["type"] for e in events].index("token")


async def test_metadata_diagnostics_is_null_when_no_search_ran():
    service = AutonomousAgentService()
    service._ensure_client = lambda: False
    raw = [e async for e in service.execute_turn_stream(db=_fake_db(), user_message="hola")]
    metadata = _events(raw)[-1]
    assert metadata["type"] == "metadata" and metadata["diagnostics"] is None
    assert metadata["duration_ms"] >= 0


async def test_sync_chat_response_carries_diagnostics_and_duration():
    service = AutonomousAgentService()
    service._ensure_client = lambda: False
    search = AsyncMock(return_value={"context_text": "ctx", "citations": [], "total_found": 1, "diagnostics": DIAG})
    with patch("app.services.agent.execute_search_knowledge_base", search):
        response = await service.execute_turn(db=_fake_db(), user_message="quien es mattia")
    assert response.diagnostics.model_dump() == DIAG
    assert response.duration_ms >= 0
    assert response.executed_tools[0].diagnostics.model_dump() == DIAG
