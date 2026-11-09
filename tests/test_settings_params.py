"""S13: hyper-parameters in Settings and AgentChatRequest. Defaults must equal the former hard-coded values."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.telemetry import telemetry_service
from app.schemas.agent import AgentChatRequest
from app.services.embedding import EmbeddingService
from app.services.ingestion import IngestionService
from app.services.rag_search import HybridSearchService
from app.services.reranker import RerankerService


@pytest.fixture
def defaults():
    """Settings built without .env so the assertions pin the code defaults."""
    return Settings(_env_file=None)


def test_defaults_equal_previous_chunking_and_pdf_constants(defaults):
    assert (defaults.PARENT_CHUNK_SIZE, defaults.PARENT_CHUNK_OVERLAP) == (1200, 120)
    assert (defaults.CHILD_CHUNK_SIZE, defaults.CHILD_CHUNK_OVERLAP) == (350, 40)
    assert defaults.PDF_IMAGE_DPI == 150
    assert defaults.PDF_MIN_IMAGE_DIM == 40


def test_defaults_equal_previous_embedding_constants(defaults):
    assert defaults.GEMINI_EMBEDDING_MODEL == "gemini-embedding-001"
    assert defaults.EMBEDDING_DIMENSION == 768
    assert defaults.EMBEDDING_BATCH_SIZE == 50


def test_defaults_equal_previous_search_and_rerank_constants(defaults):
    assert defaults.RRF_K == 60
    assert defaults.SEARCH_CANDIDATE_MULTIPLIER == 4
    assert defaults.RERANK_TIMEOUT_SECONDS == 8.0
    assert defaults.RERANK_MAX_SNIPPET_CHARS == 800


def test_defaults_equal_previous_agent_constants_and_new_flags(defaults):
    assert defaults.AGENT_MAX_HISTORY_MESSAGES == 20
    assert defaults.AGENT_MAX_TURNS == 4
    assert defaults.AGENT_TEMPERATURE == 0.2
    assert defaults.RATE_LIMIT_PER_MINUTE == 60
    assert defaults.AUTO_FALLBACK_SQLITE is True
    assert defaults.AUTO_SEED_DEMO_CORPUS is True
    assert defaults.ALLOWED_ORIGIN_REGEX == ""


# --- wiring -----------------------------------------------------------------
LONG_TEXT = ("palabra " * 600).strip()


def test_ingestion_chunk_sizes_come_from_settings(monkeypatch):
    default_longest = max(len(c) for c in IngestionService().parent_splitter.split_text(LONG_TEXT))
    assert 500 < default_longest <= 1200  # default behaviour unchanged

    monkeypatch.setattr(settings, "PARENT_CHUNK_SIZE", 300)
    monkeypatch.setattr(settings, "PARENT_CHUNK_OVERLAP", 30)
    monkeypatch.setattr(settings, "CHILD_CHUNK_SIZE", 100)
    monkeypatch.setattr(settings, "CHILD_CHUNK_OVERLAP", 10)
    service = IngestionService()
    assert max(len(c) for c in service.parent_splitter.split_text(LONG_TEXT)) <= 300
    assert max(len(c) for c in service.child_splitter.split_text(LONG_TEXT)) <= 100


def test_embedding_dimension_and_model_come_from_settings(monkeypatch):
    assert EmbeddingService().model_name == "gemini-embedding-001"
    assert len(EmbeddingService()._generate_mock_embedding("hola")) == 768
    monkeypatch.setattr(settings, "GEMINI_EMBEDDING_MODEL", "other-model")
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSION", 16)
    service = EmbeddingService()
    assert service.model_name == "other-model"
    assert len(service._generate_mock_embedding("hola")) == 16


async def test_embedding_batch_size_defaults_to_settings(monkeypatch):
    calls = []

    async def embed_content(model, contents, config=None):
        calls.append(len(contents))
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1]) for _ in contents])

    monkeypatch.setenv("GOOGLE_API_KEY", "real-test-key")
    service = EmbeddingService()
    service.api_key = "real-test-key"
    service._initialized = True
    service._client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(embed_content=embed_content)))

    await service.get_embeddings_batch([f"t{i}" for i in range(120)])
    assert calls == [50, 50, 20]  # EMBEDDING_BATCH_SIZE default = 50

    calls.clear()
    monkeypatch.setattr(settings, "EMBEDDING_BATCH_SIZE", 2)
    await service.get_embeddings_batch(["a", "b", "c", "d", "e"])
    assert calls == [2, 2, 1]


def test_rrf_k_defaults_to_settings(monkeypatch):
    dense = [{"chunk_id": uuid.uuid4()}]
    service = HybridSearchService()
    assert service.rrf_k == 60
    assert service._apply_rrf(dense, [])[0]["score"] == pytest.approx(1 / 61)
    monkeypatch.setattr(settings, "RRF_K", 10)
    assert service.rrf_k == 10
    assert service._apply_rrf(dense, [])[0]["score"] == pytest.approx(1 / 11)
    assert HybridSearchService(rrf_k=5).rrf_k == 5  # explicit argument still wins


async def test_rerank_timeout_comes_from_settings(monkeypatch):
    seen = []

    async def fake_wait_for(coro, timeout):
        seen.append(timeout)
        coro.close()
        return [{"chunk_id": 1, "rerank_score": 1.0}]

    service = RerankerService()
    service._ensure_client = lambda: True
    service._client = object()
    cands = [{"chunk_id": i, "content": "x", "document_name": "d", "score": 0.5} for i in range(2)]
    with patch.object(telemetry_service, "_enabled", False), patch(
        "app.services.reranker.asyncio.wait_for", fake_wait_for
    ):
        await service.rerank(query="q", candidates=cands, top_n=1)
        monkeypatch.setattr(settings, "RERANK_TIMEOUT_SECONDS", 3.5)
        await service.rerank(query="q", candidates=cands, top_n=1)
    assert seen == [8.0, 3.5]


async def test_rerank_snippet_length_comes_from_settings(monkeypatch):
    prompts = []

    async def generate_content(model, contents, config):
        prompts.append(contents)
        return SimpleNamespace(text='[{"index": 0, "score": 0.9}]')

    service = RerankerService()
    service._client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    cand = [{"chunk_id": 1, "content": "a" * 1000, "document_name": "d", "score": 0.5}]
    await service._score_with_gemini("q", cand, 1)
    monkeypatch.setattr(settings, "RERANK_MAX_SNIPPET_CHARS", 20)
    await service._score_with_gemini("q", cand, 1)
    assert "a" * 800 in prompts[0] and "a" * 801 not in prompts[0]
    assert "a" * 20 in prompts[1] and "a" * 21 not in prompts[1]


def test_cors_regex_is_wired_from_settings():
    from app.main import app

    cors = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    assert cors.kwargs["allow_origin_regex"] == (settings.ALLOWED_ORIGIN_REGEX or None)


# --- AgentChatRequest -------------------------------------------------------
def test_agent_request_defaults_and_validation():
    req = AgentChatRequest(message="hola")
    assert req.filter_document_id is None
    assert (req.search_mode, req.top_k, req.enable_rerank) == ("hybrid", 5, True)
    assert req.temperature is None and req.max_turns is None
    assert AgentChatRequest(message="x", search_mode="sparse", top_k=3).search_mode == "sparse"
    for bad in ({"search_mode": "fuzzy"}, {"top_k": 0}, {"top_k": 51}, {"temperature": 2.5}, {"max_turns": 0}):
        with pytest.raises(ValidationError):
            AgentChatRequest(message="x", **bad)


def _fallback_db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


async def test_agent_request_params_are_honored_by_fallback_search():
    from app.services.agent import AutonomousAgentService

    service = AutonomousAgentService()
    doc_id = uuid.uuid4()
    search = AsyncMock(return_value={"context_text": "ctx", "citations": [], "total_found": 0})
    options = AgentChatRequest(
        message="cv", search_mode="sparse", top_k=7, enable_rerank=False, filter_document_id=doc_id
    ).to_options()
    with patch("app.services.agent.execute_search_knowledge_base", search), patch.object(
        telemetry_service, "_enabled", False
    ):
        await service._execute_fallback_turn(
            db=_fallback_db(), user_message="cv de mattia", session_id=uuid.uuid4(), options=options
        )
    kwargs = search.await_args.kwargs
    assert (kwargs["mode"], kwargs["top_k"], kwargs["rerank"], kwargs["filter_document_id"]) == (
        "sparse", 7, False, doc_id,
    )


async def test_unset_agent_params_keep_previous_fallback_behaviour():
    from app.services.agent import AutonomousAgentService

    service = AutonomousAgentService()
    search = AsyncMock(return_value={"context_text": "ctx", "citations": [], "total_found": 0})
    with patch("app.services.agent.execute_search_knowledge_base", search), patch.object(
        telemetry_service, "_enabled", False
    ):
        await service._execute_fallback_turn(
            db=_fallback_db(), user_message="cv de mattia", session_id=uuid.uuid4(),
            options=AgentChatRequest(message="cv de mattia").to_options(),
        )
    kwargs = search.await_args.kwargs
    assert kwargs["top_k"] == 3  # former hard-coded fallback value
    assert kwargs["mode"] == "hybrid" and kwargs["rerank"] is True


async def test_sparse_search_mode_skips_dense_retrieval(monkeypatch):
    from app.services.rag_search import hybrid_search_service
    from app.tools.rag_tool import execute_search_knowledge_base

    dense = AsyncMock(return_value=[])
    sparse = AsyncMock(return_value=[])
    embed = AsyncMock(return_value=[0.0])
    monkeypatch.setattr(hybrid_search_service, "_dense_retrieval", dense)
    monkeypatch.setattr(hybrid_search_service, "_sparse_retrieval", sparse)
    monkeypatch.setattr("app.services.rag_search.embedding_service.get_embedding", embed)

    await execute_search_knowledge_base(db=MagicMock(), query="hola", top_k=3, mode="sparse", rerank=False)
    assert dense.await_count == 0 and embed.await_count == 0
    assert sparse.await_count == 1


def _looping_service(configs, contents_seen):
    from app.services.agent import AutonomousAgentService

    service = AutonomousAgentService()
    service._client = object()
    service._ensure_client = lambda: True

    async def fake_call(contents, config, preferred_model=None):
        configs.append(config)
        contents_seen.append(list(contents))
        call = SimpleNamespace(name="search_knowledge_base", args={"query": "q"})
        fake_content = SimpleNamespace(role="model", parts=[])
        response = SimpleNamespace(
            function_calls=[call], candidates=[SimpleNamespace(content=fake_content)], text=None, usage_metadata=None
        )
        return response, "m"

    service._call_gemini_with_fallback = fake_call
    service._dispatch_tool_call = AsyncMock(return_value=("r", []))
    return service


async def _run_turn(service, history=(), options=None):
    return await service._execute_gemini_turn(
        db=MagicMock(), user_message="x", session_id=uuid.uuid4(), prior_messages=list(history), options=options
    )


async def test_agent_turns_and_temperature_default_then_request_then_settings(monkeypatch):
    configs, seen = [], []
    with patch.object(telemetry_service, "_enabled", False):
        await _run_turn(_looping_service(configs, seen))
        assert len(configs) == 4 and configs[0].temperature == 0.2  # previous hard-coded values

        configs.clear()
        options = AgentChatRequest(message="x", max_turns=2, temperature=0.9).to_options()
        await _run_turn(_looping_service(configs, seen), options=options)
        assert len(configs) == 2 and configs[0].temperature == 0.9

        configs.clear()
        monkeypatch.setattr(settings, "AGENT_MAX_TURNS", 1)
        monkeypatch.setattr(settings, "AGENT_TEMPERATURE", 0.5)
        await _run_turn(_looping_service(configs, seen))
        assert len(configs) == 1 and configs[0].temperature == 0.5


async def test_agent_history_window_comes_from_settings(monkeypatch):
    from app.models.chat import ChatMessage

    configs, seen = [], []
    history = [ChatMessage(session_id=uuid.uuid4(), role="user", content=f"m{i}") for i in range(6)]
    monkeypatch.setattr(settings, "AGENT_MAX_HISTORY_MESSAGES", 2)
    monkeypatch.setattr(settings, "AGENT_MAX_TURNS", 1)
    with patch.object(telemetry_service, "_enabled", False):
        await _run_turn(_looping_service(configs, seen), history=history)
    assert [c.parts[0].text for c in seen[0]] == ["m4", "m5", "x"]


def test_default_gemini_models_are_not_retired(monkeypatch):
    """Code defaults must point to a served model, not the retired gemini-1.5-* family."""
    monkeypatch.delenv("GEMINI_AGENT_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_VISION_MODEL", raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.GEMINI_AGENT_MODEL == "gemini-3.8-flash"
    assert defaults.GEMINI_VISION_MODEL == "gemini-3.8-flash"
