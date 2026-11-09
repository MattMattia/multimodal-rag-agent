"""Backend i18n (es/en): language resolution, agent prompt/fallback, PDF + Markdown labels, evaluation warnings."""

import io
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pdfplumber
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core import i18n
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.chat import ChatMessage, ensure_chat_schema
from app.schemas.agent import AgentChatRequest
from app.services.agent import AutonomousAgentService
from app.tools.pdf_generator import build_conversation_pdf, execute_generate_report_pdf

ES_LABELS = {
    "executive_summary": "Resumen Ejecutivo",
    "key_takeaways": "Puntos Clave",
    "generated_on": "Generado el",
    "session_export": "Exportación de Sesión",
    "user": "Usuario",
    "agent": "Agente",
    "cited_sources": "Fuentes Citadas",
}
EN_LABELS = {
    "executive_summary": "Executive Summary",
    "key_takeaways": "Key Takeaways",
    "generated_on": "Generated on",
    "session_export": "Session Export",
    "user": "User",
    "agent": "Agent",
    "cited_sources": "Cited Sources",
}


@pytest.fixture
def http():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def open_api(monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "")


def _pdf_text(data: bytes) -> str:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


# --- language detection -------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("¿Cuál es el resumen del documento?", "es"),
        ("Dame la experiencia de Mattia", "es"),
        ("What is the total amount of the invoice?", "en"),
        ("Please summarize the audit report", "en"),
        ("hello", "en"),
        ("", "es"),
        ("   ", "es"),
        ("PDF 2024", "es"),  # undecidable -> default
        ("12345 ???", "es"),
    ],
)
def test_detect_language(text, expected):
    assert i18n.detect_language(text) == expected


def test_resolve_language_respects_explicit_choice_and_detects_on_auto():
    assert i18n.resolve_language("es", "What is this?") == "es"
    assert i18n.resolve_language("en", "¿Qué es esto?") == "en"
    assert i18n.resolve_language("auto", "What is this?") == "en"
    assert i18n.resolve_language("auto", "¿Qué es esto?") == "es"
    assert i18n.resolve_language(None, "") == "es"


def test_labels_are_exactly_the_contracted_strings():
    for key, value in ES_LABELS.items():
        assert i18n.labels("es")[key] == value
    for key, value in EN_LABELS.items():
        assert i18n.labels("en")[key] == value
    assert i18n.labels("fr") == i18n.labels("es")


def test_request_schema_language_defaults_to_auto_and_flows_into_options():
    assert AgentChatRequest(message="hi").language == "auto"
    assert AgentChatRequest(message="hi").to_options().language == "auto"
    assert AgentChatRequest(message="hi", language="en").to_options().language == "en"
    with pytest.raises(ValueError):
        AgentChatRequest(message="hi", language="fr")


# --- chat endpoint in no-key fallback mode -------------------------------------------------------
@pytest.mark.asyncio
async def test_chat_fallback_text_follows_requested_language(http):
    async with http as client:
        es = await client.post("/api/v1/agent/chat", json={"message": "hola mundo", "language": "es"})
        en = await client.post("/api/v1/agent/chat", json={"message": "hola mundo", "language": "en"})
        auto_en = await client.post("/api/v1/agent/chat", json={"message": "hello world"})
        default = await client.post("/api/v1/agent/chat", json={"message": "hola mundo"})
    assert es.status_code == en.status_code == 200
    assert es.json()["response"] == "He procesado tu solicitud: 'hola mundo'."
    assert en.json()["response"] == "I have processed your request: 'hola mundo'."
    assert auto_en.json()["response"] == "I have processed your request: 'hello world'."
    assert default.json()["response"] == es.json()["response"]


@pytest.mark.asyncio
async def test_chat_stream_fallback_follows_requested_language(http):
    async with http as client:
        resp = await client.post("/api/v1/agent/chat/stream", json={"message": "hola", "language": "en"})
    tokens = "".join(
        p["content"]
        for p in (json.loads(line[6:]) for line in resp.text.split("\n\n") if line.startswith("data: "))
        if p["type"] == "token"
    )
    assert tokens == "I have processed your request: 'hola'."


@pytest.mark.asyncio
async def test_fallback_turn_localizes_search_failure_and_pdf_notice():
    service = AutonomousAgentService()
    search = AsyncMock(return_value={"context_text": "", "citations": [], "total_found": 0})
    pdf = MagicMock(return_value={"filename": "r.pdf", "download_url": "/uploads/reports/r.pdf"})
    from app.schemas.agent import AgentOptions

    with patch("app.services.agent.execute_search_knowledge_base", search), patch(
        "app.services.agent.execute_generate_report_pdf", pdf
    ):
        result = await service._execute_fallback_turn(
            db=MagicMock(),
            user_message="pdf report about the cv",
            session_id=uuid.uuid4(),
            options=AgentOptions(language="en"),
        )
    assert "The executive PDF report has been generated" in result.response
    assert pdf.call_args.kwargs["language"] == "en"
    assert pdf.call_args.kwargs["title"] == "Executive Knowledge Report"


@pytest.mark.asyncio
async def test_fallback_turn_default_pdf_text_stays_spanish():
    service = AutonomousAgentService()
    search = AsyncMock(return_value={"context_text": "", "citations": [], "total_found": 0})
    pdf = MagicMock(return_value={"filename": "r.pdf", "download_url": "/u/r.pdf"})
    with patch("app.services.agent.execute_search_knowledge_base", search), patch(
        "app.services.agent.execute_generate_report_pdf", pdf
    ):
        result = await service._execute_fallback_turn(
            db=MagicMock(), user_message="genera un informe en pdf", session_id=uuid.uuid4()
        )
    assert "Se ha generado el informe ejecutivo en PDF" in result.response
    assert pdf.call_args.kwargs["title"] == "Informe Ejecutivo de Conocimiento"
    assert pdf.call_args.kwargs["language"] == "es"


# --- Gemini path: language instruction in the system prompt --------------------------------------
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


def _gemini_service() -> AutonomousAgentService:
    service = AutonomousAgentService()
    service._client = object()
    service._ensure_client = lambda: True  # type: ignore[method-assign]
    response = SimpleNamespace(function_calls=None, candidates=[], text="ok", usage_metadata=None)
    service._call_gemini_with_fallback = AsyncMock(return_value=(response, "fake"))  # type: ignore[method-assign]
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "language,message,needle",
    [("en", "hola", "ALWAYS answer in English"), ("es", "hello", "responde SIEMPRE en español"),
     ("auto", "What is the revenue?", "ALWAYS answer in English"), ("auto", "¿Cuál es el ingreso?", "responde SIEMPRE en español")],
)
async def test_gemini_sync_system_prompt_carries_language_instruction(language, message, needle):
    from app.schemas.agent import AgentOptions

    service = _gemini_service()
    await service.execute_turn(db=_fake_db(), user_message=message, options=AgentOptions(language=language))
    config = service._call_gemini_with_fallback.call_args.kwargs["config"]
    assert needle in config.system_instruction
    assert "generate_report_pdf" in config.system_instruction  # base prompt preserved


@pytest.mark.asyncio
async def test_gemini_stream_system_prompt_carries_language_instruction():
    from app.schemas.agent import AgentOptions

    service = _gemini_service()
    events = [
        e
        async for e in service.execute_turn_stream(
            db=_fake_db(), user_message="hola", options=AgentOptions(language="en")
        )
    ]
    config = service._call_gemini_with_fallback.call_args.kwargs["config"]
    assert "ALWAYS answer in English" in config.system_instruction
    assert events[-1].startswith("data: ")


@pytest.mark.asyncio
async def test_gemini_failure_notice_is_localized_in_sync_mode():
    from app.schemas.agent import AgentOptions

    service = _gemini_service()
    service._call_gemini_with_fallback = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]
    result = await service.execute_turn(
        db=_fake_db(), user_message="hello there", options=AgentOptions(language="en")
    )
    assert "System notice: The Gemini API did not respond in time" in result.response
    assert "I have processed your request" in result.response


# --- PDF generator -------------------------------------------------------------------------------
@pytest.mark.parametrize("lang,labels", [("es", ES_LABELS), ("en", EN_LABELS)])
def test_generate_report_pdf_uses_language_labels(lang, labels):
    info = execute_generate_report_pdf(
        title="Informe", summary="Resumen del caso", key_points=["uno"], language=lang
    )
    from pathlib import Path

    path = Path(info["file_path"])
    try:
        data = path.read_bytes()
    finally:
        path.unlink(missing_ok=True)
    assert data.startswith(b"%PDF-")
    text = _pdf_text(data)
    assert labels["executive_summary"] in text
    assert labels["key_takeaways"] in text
    assert labels["generated_on"] in text
    other = EN_LABELS if lang == "es" else ES_LABELS
    assert other["executive_summary"] not in text
    assert info["filename"].startswith("reporte_" if lang == "es" else "report_")


def test_generate_report_pdf_defaults_to_spanish():
    info = execute_generate_report_pdf(title="T", summary="S")
    from pathlib import Path

    path = Path(info["file_path"])
    try:
        text = _pdf_text(path.read_bytes())
    finally:
        path.unlink(missing_ok=True)
    assert "Resumen Ejecutivo" in text
    assert info["filename"].startswith("reporte_")
    assert info["message"] == "Reporte PDF 'T' generado exitosamente."


MESSAGES = [
    {"role": "user", "content": "Pregunta", "citations": [], "executed_tools": []},
    {
        "role": "assistant",
        "content": "Respuesta",
        "citations": [{"document_name": "informe.pdf", "page_number": 3}],
        "executed_tools": [{"tool_name": "search_knowledge_base", "tool_input": {"query": "q"}}],
    },
]


@pytest.mark.parametrize("lang,labels", [("es", ES_LABELS), ("en", EN_LABELS)])
def test_build_conversation_pdf_uses_language_labels(lang, labels):
    data = build_conversation_pdf(uuid.uuid4(), MESSAGES, lang)
    assert data.startswith(b"%PDF-")
    text = _pdf_text(data)
    for key in ("session_export", "generated_on", "user", "agent", "cited_sources"):
        assert labels[key] in text, key
    other = EN_LABELS if lang == "es" else ES_LABELS
    assert other["session_export"] not in text
    assert "informe.pdf" in text and "search_knowledge_base" in text


def test_build_conversation_pdf_defaults_to_spanish():
    text = _pdf_text(build_conversation_pdf(uuid.uuid4(), MESSAGES))
    assert "Exportación de Sesión" in text and "Usuario" in text


# --- export endpoint -----------------------------------------------------------------------------
@pytest.fixture
async def session_id():
    await ensure_chat_schema()
    sid = uuid.uuid4()
    t0 = datetime(2030, 1, 1, tzinfo=UTC)
    async with AsyncSessionLocal() as db:
        for i, (role, content, cits, tools) in enumerate(
            [
                ("user", "Pregunta", [], []),
                ("assistant", "Respuesta", [{"document_name": "informe.pdf", "page_number": 3, "chunk_type": "text"}],
                 [{"tool_name": "search_knowledge_base", "tool_input": {}, "tool_output": "ok"}]),
            ]
        ):
            db.add(ChatMessage(session_id=sid, role=role, content=content, citations=cits,
                               executed_tools=tools, created_at=t0 + timedelta(minutes=i)))
        await db.commit()
    yield sid
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ChatMessage).where(ChatMessage.session_id == sid))
        await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("lang,labels", [("es", ES_LABELS), ("en", EN_LABELS)])
async def test_export_markdown_labels_follow_lang(http, session_id, lang, labels):
    async with http as client:
        resp = await client.get(f"/api/v1/agent/sessions/{session_id}/export", params={"lang": lang})
    assert resp.status_code == 200
    body = resp.text
    assert f"# {labels['session_export']} {session_id}" in body
    assert f"## {labels['user']} (" in body and f"## {labels['agent']} (" in body
    assert f"**{labels['cited_sources']}:**" in body
    other = EN_LABELS if lang == "es" else ES_LABELS
    assert other["session_export"] not in body


@pytest.mark.asyncio
async def test_export_default_lang_is_spanish_and_invalid_lang_is_422(http, session_id):
    async with http as client:
        default = await client.get(f"/api/v1/agent/sessions/{session_id}/export")
        es = await client.get(f"/api/v1/agent/sessions/{session_id}/export", params={"lang": "es"})
        bad = await client.get(f"/api/v1/agent/sessions/{session_id}/export", params={"lang": "fr"})
    assert default.text == es.text
    assert "Exportación de Sesión" in default.text
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_export_pdf_lang_en_renders_english_labels(http, session_id):
    async with http as client:
        resp = await client.get(
            f"/api/v1/agent/sessions/{session_id}/export", params={"format": "pdf", "lang": "en"}
        )
    assert resp.status_code == 200 and resp.content.startswith(b"%PDF-")
    text = _pdf_text(resp.content)
    assert "Session Export" in text and "Cited Sources" in text and "User" in text


# --- evaluation warnings -------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_evaluate_warnings_follow_lang(http, sqlite_db, demo_dirs):
    async with http as client:
        await client.post("/api/v1/demo/seed")
        default = await client.post("/api/v1/demo/evaluate")
        es = await client.post("/api/v1/demo/evaluate", params={"lang": "es"})
        en = await client.post("/api/v1/demo/evaluate", params={"lang": "en"})
        bad = await client.post("/api/v1/demo/evaluate", params={"lang": "fr"})
    assert default.status_code == es.status_code == en.status_code == 200
    assert any("Embeddings simulados" in w for w in default.json()["warnings"])
    assert any("Embeddings simulados" in w for w in es.json()["warnings"])
    assert any("Simulated embeddings" in w and "SHA-256" in w for w in en.json()["warnings"])
    assert set(en.json()["modes"]) == set(es.json()["modes"]) == {"dense", "sparse", "hybrid"}
    assert bad.status_code == 422
