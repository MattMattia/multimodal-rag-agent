"""Session lifecycle, export and feedback endpoints of the agent (R2-BUG-07)."""

import io
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pdfplumber
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.telemetry import telemetry_service
from app.main import app
from app.models.chat import ChatMessage, ensure_chat_schema

T0 = datetime(2030, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
async def _schema_and_open_api(monkeypatch):
    await ensure_chat_schema()
    monkeypatch.setattr(settings, "API_KEY", "")


@pytest.fixture
def http():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def sessions():
    """Tracks created session ids and deletes their messages afterwards."""
    ids = []
    yield ids
    async with AsyncSessionLocal() as db:
        await db.execute(delete(ChatMessage).where(ChatMessage.session_id.in_(ids)))
        await db.commit()


async def _seed(ids, rows, session_id=None):
    """rows: list of (role, content, minutes_offset, citations, tools). Returns (session_id, [message ids])."""
    session_id = session_id or uuid.uuid4()
    ids.append(session_id)
    message_ids = []
    async with AsyncSessionLocal() as db:
        for role, content, minutes, citations, tools in rows:
            msg = ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                citations=citations,
                executed_tools=tools,
                created_at=T0 + timedelta(minutes=minutes),
            )
            db.add(msg)
            await db.flush()
            message_ids.append(msg.id)
        await db.commit()
    return session_id, message_ids


CITATION = {"document_name": "informe.pdf", "page_number": 3, "chunk_type": "text"}
TOOL = {"tool_name": "search_knowledge_base", "tool_input": {"query": "q"}, "tool_output": "ok"}


# ---------------------------------------------------------------------------
# GET /agent/sessions
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_list_sessions_summaries_ordered_by_updated_at_desc(http, sessions):
    long_title = "x" * 120
    old_id, _ = await _seed(sessions, [
        ("assistant", "hola, soy el agente", 0, [], []),
        ("user", long_title, 1, [], []),
        ("assistant", "respuesta", 2, [], []),
    ])
    new_id, _ = await _seed(sessions, [
        ("user", "pregunta corta", 10, [], []),
        ("assistant", "respuesta corta", 20, [], []),
    ])
    async with http as client:
        resp = await client.get("/api/v1/agent/sessions")
    assert resp.status_code == 200
    items = resp.json()
    by_id = {i["session_id"]: i for i in items}
    old, new = by_id[str(old_id)], by_id[str(new_id)]

    assert old["title"] == "x" * 80
    assert old["message_count"] == 3
    assert old["created_at"].startswith("2030-01-01T00:00:00")
    assert old["updated_at"].startswith("2030-01-01T00:02:00")
    assert new["title"] == "pregunta corta"
    assert new["message_count"] == 2
    assert new["updated_at"].startswith("2030-01-01T00:20:00")
    ids_in_order = [i["session_id"] for i in items]
    assert ids_in_order.index(str(new_id)) < ids_in_order.index(str(old_id))
    updated = [i["updated_at"] for i in items]
    assert updated == sorted(updated, reverse=True)


# ---------------------------------------------------------------------------
# DELETE /agent/sessions/{id}
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_delete_session_removes_only_its_messages(http, sessions):
    target, _ = await _seed(sessions, [("user", "a", 0, [], []), ("assistant", "b", 1, [], [])])
    other, _ = await _seed(sessions, [("user", "keep", 0, [], [])])
    async with http as client:
        first = await client.delete(f"/api/v1/agent/sessions/{target}")
        again = await client.delete(f"/api/v1/agent/sessions/{target}")
        history = await client.get(f"/api/v1/agent/sessions/{target}/history")
        other_history = await client.get(f"/api/v1/agent/sessions/{other}/history")
    assert first.status_code == 204
    assert first.content == b""
    assert again.status_code == 404
    assert history.json()["total_messages"] == 0
    assert other_history.json()["total_messages"] == 1


# ---------------------------------------------------------------------------
# GET /agent/sessions/{id}/export
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_export_markdown_contains_conversation_citations_and_tools(http, sessions):
    sid, _ = await _seed(sessions, [
        ("user", "¿Cuál fue el EBITDA?", 0, [], []),
        ("assistant", "El EBITDA fue 34%.", 1, [CITATION], [TOOL]),
    ])
    async with http as client:
        resp = await client.get(f"/api/v1/agent/sessions/{sid}/export", params={"format": "markdown"})
        default = await client.get(f"/api/v1/agent/sessions/{sid}/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert resp.headers["content-disposition"] == f'attachment; filename="session-{sid}.md"'
    body = resp.text
    assert "¿Cuál fue el EBITDA?" in body
    assert "El EBITDA fue 34%." in body
    assert "informe.pdf" in body and "3" in body
    assert "search_knowledge_base" in body
    assert body.index("¿Cuál fue el EBITDA?") < body.index("El EBITDA fue 34%.")
    assert default.status_code == 200
    assert default.text == body


@pytest.mark.asyncio
async def test_export_pdf_is_generated_in_a_thread_and_escapes_markup(http, sessions):
    sid, _ = await _seed(sessions, [
        ("user", "Texto con <b>marcado</b> & símbolos", 0, [], []),
        ("assistant", "Respuesta final", 1, [CITATION], [TOOL]),
    ])
    real_to_thread = __import__("asyncio").to_thread
    calls = []

    async def spy(func, *args, **kwargs):
        calls.append(func)
        return await real_to_thread(func, *args, **kwargs)

    with patch("app.api.v1.endpoints.agent.asyncio.to_thread", spy):
        async with http as client:
            resp = await client.get(f"/api/v1/agent/sessions/{sid}/export", params={"format": "pdf"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"] == f'attachment; filename="session-{sid}.pdf"'
    assert resp.content.startswith(b"%PDF-")
    assert len(calls) == 1
    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "<b>marcado</b>" in text
    assert "Respuesta final" in text
    assert "informe.pdf" in text
    assert "search_knowledge_base" in text


@pytest.mark.asyncio
async def test_export_unknown_session_404_and_invalid_format_422(http, sessions):
    sid, _ = await _seed(sessions, [("user", "a", 0, [], [])])
    async with http as client:
        unknown = await client.get(f"/api/v1/agent/sessions/{uuid.uuid4()}/export")
        invalid = await client.get(f"/api/v1/agent/sessions/{sid}/export", params={"format": "docx"})
    assert unknown.status_code == 404
    assert invalid.status_code == 422


# ---------------------------------------------------------------------------
# POST /agent/feedback
# ---------------------------------------------------------------------------
async def _metadata(message_id):
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(ChatMessage.message_metadata).where(ChatMessage.id == message_id))
        return res.scalar_one()


@pytest.mark.asyncio
async def test_feedback_is_stored_in_message_metadata(http, sessions):
    sid, (_, assistant_id) = await _seed(sessions, [("user", "q", 0, [], []), ("assistant", "a", 1, [], [])])
    async with http as client:
        resp = await client.post("/api/v1/agent/feedback", json={
            "session_id": str(sid), "message_id": str(assistant_id), "rating": -1, "comment": "incorrecto",
        })
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "message_id": str(assistant_id), "rating": -1}
    metadata = await _metadata(assistant_id)
    assert metadata["feedback"]["rating"] == -1
    assert metadata["feedback"]["comment"] == "incorrecto"


@pytest.mark.asyncio
async def test_feedback_validation_and_not_found(http, sessions):
    sid, (message_id,) = await _seed(sessions, [("assistant", "a", 0, [], [])])
    other_sid = uuid.uuid4()
    async with http as client:
        bad_rating = await client.post("/api/v1/agent/feedback", json={
            "session_id": str(sid), "message_id": str(message_id), "rating": 0})
        unknown = await client.post("/api/v1/agent/feedback", json={
            "session_id": str(sid), "message_id": str(uuid.uuid4()), "rating": 1})
        wrong_session = await client.post("/api/v1/agent/feedback", json={
            "session_id": str(other_sid), "message_id": str(message_id), "rating": 1})
    assert bad_rating.status_code == 422
    assert unknown.status_code == 404
    assert wrong_session.status_code == 404
    assert (await _metadata(message_id) or {}).get("feedback") is None


@pytest.mark.asyncio
async def test_feedback_sends_langfuse_score_only_when_telemetry_enabled(http, sessions):
    sid, (message_id,) = await _seed(sessions, [("assistant", "a", 0, [], [])])
    payload = {"session_id": str(sid), "message_id": str(message_id), "rating": 1, "comment": "genial"}
    client_mock = MagicMock()
    async with http as client:
        with patch.object(telemetry_service, "_enabled", False), patch.object(telemetry_service, "_client", client_mock):
            disabled = await client.post("/api/v1/agent/feedback", json=payload)
        client_mock.score.assert_not_called()
        with patch.object(telemetry_service, "_enabled", True), patch.object(telemetry_service, "_client", client_mock):
            enabled = await client.post("/api/v1/agent/feedback", json=payload)
    assert disabled.status_code == 200 and enabled.status_code == 200
    client_mock.score.assert_called_once()
    kwargs = client_mock.score.call_args.kwargs
    assert kwargs["name"] == "user_feedback"
    assert kwargs["value"] == 1
    assert kwargs["comment"] == "genial"
