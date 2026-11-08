"""EmbeddingService retries and mock-vector policy (R2-BUG-03)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.services import embedding as embedding_module
from app.services.embedding import EmbeddingService

REAL_VECTOR = [1.0] + [0.0] * 767  # already unit-length, so normalization keeps it unchanged


def _configured_service(monkeypatch, embed_mock):
    """A service that believes a real GOOGLE_API_KEY is configured and uses `embed_mock` as the Gemini call."""
    monkeypatch.setenv("GOOGLE_API_KEY", "real-test-key")
    service = EmbeddingService()
    service.api_key = "real-test-key"
    service._initialized = True
    service._client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(embed_content=embed_mock)))
    return service


@pytest.fixture
def sleeps(monkeypatch):
    recorded = []

    async def fake_sleep(delay):
        recorded.append(delay)

    # Replace only the module-level name so the real asyncio.sleep (used by the event loop plumbing) is untouched.
    monkeypatch.setattr(embedding_module, "asyncio", SimpleNamespace(sleep=fake_sleep))
    return recorded


def _single(values=REAL_VECTOR):
    return SimpleNamespace(embedding=SimpleNamespace(values=values), embeddings=None)


def _batch(n):
    return SimpleNamespace(embeddings=[SimpleNamespace(values=REAL_VECTOR) for _ in range(n)])


@pytest.mark.asyncio
async def test_transient_errors_are_retried_with_exponential_backoff(monkeypatch, sleeps):
    embed = AsyncMock(side_effect=[Exception("503 UNAVAILABLE"), Exception("429 RESOURCE_EXHAUSTED"), _single()])
    service = _configured_service(monkeypatch, embed)
    vector = await service.get_embedding("hola")
    assert vector == REAL_VECTOR
    assert embed.await_count == 3
    assert sleeps == [0.5, 1.0]


@pytest.mark.asyncio
async def test_timeout_is_retried(monkeypatch, sleeps):
    embed = AsyncMock(side_effect=[TimeoutError("deadline"), _single()])
    service = _configured_service(monkeypatch, embed)
    assert await service.get_embedding("hola") == REAL_VECTOR
    assert sleeps == [0.5]


@pytest.mark.asyncio
async def test_persistent_failure_with_real_key_raises_and_never_returns_mock_vector(monkeypatch, sleeps):
    embed = AsyncMock(side_effect=Exception("503 UNAVAILABLE"))
    service = _configured_service(monkeypatch, embed)
    service._generate_mock_embedding = MagicMock(side_effect=AssertionError("mock vector used"))
    with pytest.raises(Exception, match="503"):
        await service.get_embedding("hola")
    assert embed.await_count == 4  # 1 attempt + 3 retries
    assert sleeps == [0.5, 1.0, 2.0]


@pytest.mark.asyncio
async def test_non_transient_error_is_raised_immediately(monkeypatch, sleeps):
    embed = AsyncMock(side_effect=Exception("400 INVALID_ARGUMENT"))
    service = _configured_service(monkeypatch, embed)
    with pytest.raises(Exception, match="400"):
        await service.get_embedding("hola")
    assert embed.await_count == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_batch_retries_each_batch_and_raises_on_persistent_failure(monkeypatch, sleeps):
    embed = AsyncMock(side_effect=[Exception("503"), _batch(2), _batch(1)])
    service = _configured_service(monkeypatch, embed)
    vectors = await service.get_embeddings_batch(["a", "b", "c"], batch_size=2)
    assert vectors == [REAL_VECTOR] * 3
    assert embed.await_count == 3
    assert sleeps == [0.5]

    failing = AsyncMock(side_effect=Exception("503 UNAVAILABLE"))
    service = _configured_service(monkeypatch, failing)
    service._generate_mock_embedding = MagicMock(side_effect=AssertionError("mock vector used"))
    with pytest.raises(Exception, match="503"):
        await service.get_embeddings_batch(["a"], batch_size=2)


@pytest.mark.asyncio
async def test_mock_vectors_only_when_client_is_not_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    service = EmbeddingService()
    single = await service.get_embedding("texto")
    batch = await service.get_embeddings_batch(["texto", "otro"])
    assert len(single) == 768
    assert single == service._generate_mock_embedding("texto")
    assert [len(v) for v in batch] == [768, 768]
    assert batch[0] == single


@pytest.mark.asyncio
async def test_requests_configured_output_dimensionality_and_returns_unit_vectors(monkeypatch):
    """gemini-embedding-001 defaults to 3072 dims: the call must request EMBEDDING_DIMENSION and normalize."""
    raw = [3.0, 4.0] + [0.0] * 766
    embed = AsyncMock(return_value=_single(raw))
    service = _configured_service(monkeypatch, embed)

    vector = await service.get_embedding("hola mundo")

    config = embed.await_args.kwargs["config"]
    assert config.output_dimensionality == settings.EMBEDDING_DIMENSION
    assert vector[:2] == pytest.approx([0.6, 0.8])
    assert len(vector) == 768


@pytest.mark.asyncio
async def test_batch_requests_output_dimensionality_and_normalizes(monkeypatch):
    raw = [0.0, 2.0] + [0.0] * 766
    embed = AsyncMock(return_value=SimpleNamespace(embeddings=[SimpleNamespace(values=raw)] * 2))
    service = _configured_service(monkeypatch, embed)

    vectors = await service.get_embeddings_batch(["a", "b"])

    assert embed.await_args.kwargs["config"].output_dimensionality == settings.EMBEDDING_DIMENSION
    assert [v[1] for v in vectors] == pytest.approx([1.0, 1.0])
