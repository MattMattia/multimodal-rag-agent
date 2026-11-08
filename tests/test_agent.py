from pathlib import Path
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.main import app
from app.services.agent import autonomous_agent_service
from app.services.vision import VisionService
from app.tools.pdf_generator import execute_generate_report_pdf
from app.tools.webhook_tool import execute_dispatch_webhook


def test_generate_report_pdf():
    """Valida la generación física de un archivo PDF estructurado con ReportLab."""
    title = "Informe de Auditoría de Sistemas"
    summary = "El análisis de infraestructura completó la validación con un 99.8% de disponibilidad operativa."
    key_points = [
        "Infraestructura PostgreSQL y pgvector desplegada en contenedores.",
        "Métricas de ingesta de documentos dentro de los umbrales esperados.",
    ]

    result = execute_generate_report_pdf(title=title, summary=summary, key_points=key_points)

    assert result["status"] == "success"
    assert "download_url" in result
    assert result["download_url"].startswith("/uploads/reports/")

    # Verificar existencia física del archivo
    file_path = Path(result["file_path"])
    assert file_path.exists()
    assert file_path.stat().st_size > 0

    # Limpieza del archivo de prueba
    try:
        file_path.unlink()
    except Exception:
        pass


@pytest.mark.asyncio
async def test_dispatch_webhook():
    """Validates the webhook tool against the default receiver without touching the real network."""
    import socket
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock, patch

    client = MagicMock()
    client.post = AsyncMock(return_value=SimpleNamespace(status_code=200))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    public_addr = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
    payload = {"invoice_id": "INV-1002", "amount": 1500.0, "status": "approved"}

    with patch("app.tools.webhook_tool.socket.getaddrinfo", return_value=public_addr), patch(
        "app.tools.webhook_tool.httpx.AsyncClient", MagicMock(return_value=client)
    ):
        result = await execute_dispatch_webhook(event_type="invoice_alert", payload=payload)

    client.post.assert_awaited_once()
    sent_body = client.post.await_args.kwargs["json"]
    assert sent_body["event_type"] == "invoice_alert"
    assert sent_body["data"] == payload
    assert result["status"] == "delivered"
    assert result["status_code"] == 200
    assert result["event_type"] == "invoice_alert"
    assert result["target_url"] == "https://httpbin.org/post"


@pytest.mark.asyncio
async def test_agent_execution_turn():
    """Valida el ciclo de ejecución del agente autónomo en sesión de base de datos."""
    async with AsyncSessionLocal() as db:
        response = await autonomous_agent_service.execute_turn(
            db=db,
            user_message="¿Qué experiencia tiene Mattia Risso? Genera un reporte en PDF.",
            session_id=uuid.uuid4(),
        )

        assert response.response is not None
        assert len(response.response) > 10
        assert isinstance(response.citations, list)
        assert isinstance(response.executed_tools, list)
        # Debe haber ejecutado al menos una herramienta (búsqueda o PDF)
        assert len(response.executed_tools) >= 1

        tool_names = [t.tool_name for t in response.executed_tools]
        assert "search_knowledge_base" in tool_names or "generate_report_pdf" in tool_names


@pytest.mark.asyncio
async def test_agent_chat_endpoint():
    """Valida la respuesta del endpoint POST /api/v1/agent/chat."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "message": "¿Cuál es el resumen de la auditoría y qué tecnologías se mencionan?",
            "session_id": None,
        }
        resp = await client.post("/api/v1/agent/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert "citations" in data
        assert "executed_tools" in data
        assert "session_id" in data
        assert isinstance(data["citations"], list)
        assert isinstance(data["executed_tools"], list)


@pytest.mark.asyncio
async def test_agent_chat_stream_endpoint():
    """Valida la respuesta en streaming (SSE) del endpoint POST /api/v1/agent/chat/stream."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        session_id = uuid.uuid4()
        payload = {
            "message": "Hola, genera una respuesta breve de saludo.",
            "session_id": str(session_id),
        }
        async with client.stream("POST", "/api/v1/agent/chat/stream", json=payload) as resp:
            assert resp.status_code == 200
            content_type = resp.headers.get("content-type", "")
            assert "text/event-stream" in content_type

            events = []
            async for line in resp.aiter_lines():
                line = line.strip()
                if line.startswith("data: "):
                    events.append(line[6:].strip())

            assert len(events) > 0
            # Debe incluir al menos evento de metadata o tokens
            assert any('"type": "metadata"' in ev or '"type": "token"' in ev for ev in events)


def test_gemini_model_configuration():
    """Valida que los modelos de Gemini se inicialicen leyendo las variables de entorno configuradas."""
    assert settings.GEMINI_AGENT_MODEL == "gemini-1.5-pro"
    assert settings.GEMINI_VISION_MODEL == "gemini-1.5-flash"
    assert autonomous_agent_service.model_name == settings.GEMINI_AGENT_MODEL

    vision_service = VisionService()
    assert vision_service.model_name == settings.GEMINI_VISION_MODEL


@pytest.mark.asyncio
async def test_chat_session_memory_persistence():
    """Valida la persistencia del historial conversacional multi-turno en PostgreSQL."""
    session_id = uuid.uuid4()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Turno 1: Mensaje inicial del usuario
        payload_1 = {
            "message": "¿Quién es Mattia Risso y qué experiencia tiene?",
            "session_id": str(session_id),
        }
        resp_1 = await client.post("/api/v1/agent/chat", json=payload_1)
        assert resp_1.status_code == 200
        data_1 = resp_1.json()
        assert data_1["session_id"] == str(session_id)
        assert len(data_1["response"]) > 0

        # Turno 2: Mensaje de seguimiento usando el mismo session_id
        payload_2 = {
            "message": "¿Y cuáles son sus habilidades técnicas principales en backend y bases de datos?",
            "session_id": str(session_id),
        }
        resp_2 = await client.post("/api/v1/agent/chat", json=payload_2)
        assert resp_2.status_code == 200
        data_2 = resp_2.json()
        assert data_2["session_id"] == str(session_id)

        # Consultar endpoint de historial de sesión
        hist_resp = await client.get(f"/api/v1/agent/sessions/{session_id}/history")
        assert hist_resp.status_code == 200
        history_data = hist_resp.json()

        assert history_data["session_id"] == str(session_id)
        # Debe contener al menos 4 mensajes: 2 del usuario y 2 del asistente
        assert history_data["total_messages"] == 4
        messages = history_data["messages"]
        assert len(messages) == 4

        # Validar secuencia de roles y contenidos
        assert messages[0]["role"] == "user"
        assert "Mattia Risso" in messages[0]["content"]
        assert messages[1]["role"] == "assistant"
        assert len(messages[1]["content"]) > 0

        assert messages[2]["role"] == "user"
        assert "habilidades" in messages[2]["content"]
        assert messages[3]["role"] == "assistant"
        assert len(messages[3]["content"]) > 0

        # Validar orden cronológico
        assert messages[0]["created_at"] <= messages[1]["created_at"]
        assert messages[1]["created_at"] <= messages[2]["created_at"]
        assert messages[2]["created_at"] <= messages[3]["created_at"]


# ==============================================================================
# Phase 1 audit remediation: single tool dispatch, streaming fidelity, citations
# ==============================================================================
import json as _json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from google.genai import types as _genai_types

from app.schemas.agent import CitationItem
from app.services.agent import AutonomousAgentService


@pytest.fixture
def no_langfuse():
    """Keep telemetry inert so unit tests never reach the Langfuse server."""
    from app.core.telemetry import telemetry_service

    with patch.object(telemetry_service, "_enabled", False):
        yield


def _fake_db() -> MagicMock:
    db = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = []
    result = MagicMock()
    result.scalars.return_value = scalars
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


def _tool_call_response() -> SimpleNamespace:
    content = _genai_types.Content(role="model", parts=[_genai_types.Part.from_text(text="call")])
    return SimpleNamespace(
        function_calls=[SimpleNamespace(name="search_knowledge_base", args={"query": "cv"})],
        candidates=[SimpleNamespace(content=content)],
        text=None,
        usage_metadata=None,
    )


def _text_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(function_calls=None, candidates=[], text=text, usage_metadata=None)


def _make_service(responses: list) -> AutonomousAgentService:
    service = AutonomousAgentService()
    service._client = object()
    service._ensure_client = lambda: True  # type: ignore[method-assign]
    service._call_gemini_with_fallback = AsyncMock(  # type: ignore[method-assign]
        side_effect=[(r, "fake-model") for r in responses]
    )
    service._dispatch_tool_call = AsyncMock(return_value=("tool result", []))  # type: ignore[method-assign]
    return service


async def test_sync_mode_dispatches_each_tool_call_once(no_langfuse):
    service = _make_service([_tool_call_response(), _text_response("final")])
    result = await service._execute_gemini_turn(
        db=_fake_db(), user_message="hola", session_id=uuid.uuid4(), prior_messages=[]
    )
    assert service._dispatch_tool_call.await_count == 1
    assert len(result.executed_tools) == 1
    assert result.response == "final"


async def test_stream_mode_dispatches_each_tool_call_once_and_records_every_turn(no_langfuse):
    service = _make_service([_tool_call_response(), _text_response("respuesta final")])
    with patch("app.services.agent.telemetry_service.record_generation") as record_gen:
        events = [e async for e in service.execute_turn_stream(db=_fake_db(), user_message="hola")]
    assert service._dispatch_tool_call.await_count == 1
    assert record_gen.call_count == 2
    assert events[-1].startswith("data: ") and '"type": "metadata"' in events[-1]


async def test_stream_chunks_preserve_multiline_markdown(no_langfuse):
    text = "# Titulo\n\n- item uno\n- item  dos\n\n```py\nx = 1\n```\n  indented tail \n"
    service = _make_service([_text_response(text)])
    events = [e async for e in service.execute_turn_stream(db=_fake_db(), user_message="hola")]
    payloads = [_json.loads(e[len("data: "):]) for e in events]
    tokens = [p["content"] for p in payloads if p["type"] == "token"]
    assert len(tokens) > 1
    assert "".join(tokens) == text


async def test_fallback_turn_executes_each_tool_once(no_langfuse):
    service = AutonomousAgentService()
    search = AsyncMock(return_value={"context_text": "ctx", "citations": [], "total_found": 1})
    pdf = MagicMock(return_value={"filename": "r.pdf", "download_url": "/uploads/reports/r.pdf"})
    webhook = AsyncMock(return_value={"message": "ok"})
    with patch("app.services.agent.execute_search_knowledge_base", search), patch(
        "app.services.agent.execute_generate_report_pdf", pdf
    ), patch("app.services.agent.execute_dispatch_webhook", webhook):
        await service._execute_fallback_turn(
            db=_fake_db(),
            user_message="informe del cv con alerta webhook en pdf",
            session_id=uuid.uuid4(),
        )
    assert search.await_count == 1
    assert pdf.call_count == 1
    assert webhook.await_count == 1


async def test_citations_carry_rerank_score(no_langfuse):
    service = AutonomousAgentService()
    raw = {
        "context_text": "ctx",
        "total_found": 1,
        "citations": [
            {"document_name": "a.pdf", "page_number": 1, "chunk_type": "text", "chunk_id": None, "rerank_score": 0.87}
        ],
    }
    with patch("app.services.agent.execute_search_knowledge_base", AsyncMock(return_value=raw)):
        _, dispatched = await service._dispatch_tool_call(
            db=_fake_db(), tool_name="search_knowledge_base", tool_args={"query": "x"}
        )
        fallback = await service._execute_fallback_turn(
            db=_fake_db(), user_message="cv", session_id=uuid.uuid4()
        )
    assert dispatched[0].rerank_score == 0.87
    assert fallback.citations[0].rerank_score == 0.87
    deduped = service._deduplicate_citations(
        [CitationItem(document_name="a.pdf", chunk_type="text", rerank_score=0.5)] * 2
    )
    assert len(deduped) == 1 and deduped[0].rerank_score == 0.5




# ==============================================================================
# R2-BUG-02: lossless fallback streaming without sleep, token usage in streaming
# ==============================================================================
from app.schemas.agent import AgentChatResponse

MARKDOWN_REPLY = "# Informe\n\n- item uno\n- item  dos\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n  cola con espacios \n"


def _fallback_response(text: str) -> AgentChatResponse:
    return AgentChatResponse(response=text, citations=[], executed_tools=[], session_id=uuid.uuid4())


@pytest.mark.parametrize("client_ready", [False, True])
async def test_fallback_stream_is_lossless_and_never_sleeps(no_langfuse, client_ready):
    service = AutonomousAgentService()
    service._client = object() if client_ready else None
    service._ensure_client = lambda: client_ready  # type: ignore[method-assign]
    service._call_gemini_with_fallback = AsyncMock(side_effect=RuntimeError("gemini down"))  # type: ignore[method-assign]
    service._execute_fallback_turn = AsyncMock(return_value=_fallback_response(MARKDOWN_REPLY))  # type: ignore[method-assign]
    sleep = AsyncMock()

    with patch("app.services.agent.asyncio", SimpleNamespace(sleep=sleep)):
        events = [e async for e in service.execute_turn_stream(db=_fake_db(), user_message="hola")]

    payloads = [_json.loads(e[len("data: "):]) for e in events]
    tokens = [p["content"] for p in payloads if p["type"] == "token"]
    assert "".join(tokens) == MARKDOWN_REPLY
    assert len(tokens) > 1
    assert any("\n\n" in t for t in tokens)
    assert payloads[-1]["type"] == "metadata"
    sleep.assert_not_awaited()


async def test_stream_records_token_usage_from_usage_metadata(no_langfuse):
    response = _text_response("respuesta")
    response.usage_metadata = SimpleNamespace(prompt_token_count=11, candidates_token_count=7, total_token_count=18)
    service = _make_service([response])
    with patch("app.services.agent.telemetry_service.record_generation") as record_gen:
        _ = [e async for e in service.execute_turn_stream(db=_fake_db(), user_message="hola")]
    assert record_gen.call_args.kwargs["usage"] == {"input": 11, "output": 7, "total": 18}


async def test_stream_usage_is_none_without_usage_metadata(no_langfuse):
    service = _make_service([_text_response("respuesta")])
    with patch("app.services.agent.telemetry_service.record_generation") as record_gen:
        _ = [e async for e in service.execute_turn_stream(db=_fake_db(), user_message="hola")]
    assert record_gen.call_args.kwargs["usage"] is None
