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
    """Valida la ejecución de la herramienta de webhooks con httpx y simulación."""
    result = await execute_dispatch_webhook(
        event_type="invoice_alert",
        payload={"invoice_id": "INV-1002", "amount": 1500.0, "status": "approved"},
    )
    assert result["status"] in ("delivered", "simulated", "warning")
    assert result["event_type"] == "invoice_alert"
    assert "status_code" in result


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


