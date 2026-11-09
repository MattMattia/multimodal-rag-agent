"""Gemini model cascade order in agent, reranker and vision services (R2-BUG-03)."""

from types import SimpleNamespace

import pytest
from PIL import Image

from app.services.agent import AutonomousAgentService
from app.services.reranker import RerankerService
from app.services.vision import VisionService

MODERN_CASCADE = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]


def _preferred_then_cascade(preferred: str) -> list[str]:
    """Expected try order: the configured model first, then the cascade, without repeating a model."""
    return list(dict.fromkeys([preferred, *MODERN_CASCADE]))


class _RecordingClient:
    """Fake Gemini client whose every call fails with a 404 and records the model it was asked for."""

    def __init__(self):
        self.models_tried = []

        async def generate_content(model, **kwargs):
            self.models_tried.append(model)
            raise Exception("404 NOT_FOUND")

        async def generate_content_stream(model, **kwargs):
            self.models_tried.append(model)
            raise Exception("404 NOT_FOUND")

        self.aio = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=generate_content, generate_content_stream=generate_content_stream
            )
        )


@pytest.mark.asyncio
async def test_agent_sync_cascade_order():
    service = AutonomousAgentService()
    service._client = client = _RecordingClient()
    with pytest.raises(Exception, match="404"):
        await service._call_gemini_with_fallback(contents=[], config=None)
    assert client.models_tried == _preferred_then_cascade(service.model_name)


@pytest.mark.asyncio
async def test_agent_stream_cascade_order():
    service = AutonomousAgentService()
    service._client = client = _RecordingClient()
    with pytest.raises(Exception, match="404"):
        _ = [t async for t in service._call_gemini_stream_with_fallback(contents=[], config=None)]
    assert client.models_tried == _preferred_then_cascade(service.model_name)


@pytest.mark.asyncio
async def test_agent_cascade_deduplicates_preferred_model_already_in_list():
    service = AutonomousAgentService()
    service._client = client = _RecordingClient()
    with pytest.raises(Exception, match="404"):
        await service._call_gemini_with_fallback(contents=[], config=None, preferred_model="gemini-2.5-flash")
    assert client.models_tried == ["gemini-2.5-flash", "gemini-3.8-flash", "gemini-3.6-flash",
                                   "gemini-3.5-flash-lite", "gemini-2.5-pro"]


@pytest.mark.asyncio
async def test_reranker_cascade_order():
    service = RerankerService()
    service._client = client = _RecordingClient()
    candidates = [{"content": "a", "document_name": "d", "score": 0.5}, {"content": "b", "document_name": "d", "score": 0.4}]
    with pytest.raises(RuntimeError, match="Ningún modelo"):
        await service._score_with_gemini(query="q", candidates=candidates, top_n=2)
    assert client.models_tried == _preferred_then_cascade(service.model_name)


@pytest.mark.asyncio
async def test_vision_cascade_order(tmp_path):
    png = tmp_path / "x.png"
    Image.new("RGB", (10, 10)).save(png)
    service = VisionService()
    service._ensure_client = lambda: None  # type: ignore[method-assign]
    service._initialized = True
    service._client = client = _RecordingClient()
    result = await service.describe_image(str(png))
    assert client.models_tried == _preferred_then_cascade(service.model_name)
    assert result.startswith("[Error al procesar imagen")
