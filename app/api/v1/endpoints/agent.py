import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Literal
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import error_detail
from app.core.telemetry import telemetry_service
from app.models.chat import ChatMessage
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    ChatHistoryResponse,
    ChatMessageResponse,
    FeedbackRequest,
    FeedbackResponse,
    SessionSummary,
)
from app.services.agent import autonomous_agent_service
from app.tools.pdf_generator import build_conversation_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/chat/stream",
    summary="Interacción conversacional con streaming en tiempo real (SSE) del Agente IA",
)
async def chat_with_agent_stream(
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Retorna una respuesta de streaming en tiempo real (Server-Sent Events) del Agente IA.

    Emite eventos estructurados:
    - `data: {"type": "token", "content": "..."}\\n\\n` para cada fragmento de texto sintetizado.
    - `data: {"type": "tool_end", "tool_name": "...", "duration_ms": 12.3, "diagnostics": {...}|null}\\n\\n` al terminar cada herramienta
      (`diagnostics` = rayos X de latencia de la búsqueda RAG, `null` para otras herramientas).
    - `data: {"type": "metadata", "citations": [...], "executed_tools": [...], "session_id": "...", "diagnostics": {...}|null, "duration_ms": 123.4}\\n\\n` al concluir la respuesta.
    """
    return StreamingResponse(
        autonomous_agent_service.execute_turn_stream(
            db=db,
            user_message=request.message,
            session_id=request.session_id,
            options=request.to_options(),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Interacción conversacional y ejecución de acciones con el Agente IA",
)
async def chat_with_agent(
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Permite interactuar con el Agente IA Autónomo empresarial.

    El agente es capaz de:
    - **Razonar:** Evalúa la intención del usuario y planifica las acciones necesarias.
    - **Consultar RAG (`search_knowledge_base`):** Recupera información semántica/léxica de documentos (PDFs, tablas, imágenes, facturas, CVs) e incluye citas explícitas en su respuesta.
    - **Generar Reportes (`generate_report_pdf`):** Maqueta y genera archivos PDF ejecutivos guardados en `/uploads/reports/` con enlace de descarga.
    - **Despachar Notificaciones (`dispatch_webhook`):** Envía webhooks HTTP POST a sistemas externos (Slack, Jira, ERP).
    - **Memoria Conversacional:** Persiste tanto la consulta del usuario como la respuesta del agente asociadas al `session_id`.
    """
    try:
        response = await autonomous_agent_service.execute_turn(
            db=db,
            user_message=request.message,
            session_id=request.session_id,
            options=request.to_options(),
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error en la ejecución del Agente IA: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("Error interno durante la ejecución del agente", e),
        )


@router.get(
    "/sessions/{session_id}/history",
    response_model=ChatHistoryResponse,
    summary="Recuperar historial conversacional persistente de una sesión",
)
async def get_session_history(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retorna la lista cronológica de mensajes (usuario y asistente) almacenados en PostgreSQL para un `session_id` específico."""
    try:
        query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        result = await db.execute(query)
        messages = list(result.scalars().all())

        return ChatHistoryResponse(
            session_id=session_id,
            total_messages=len(messages),
            messages=[ChatMessageResponse.model_validate(m) for m in messages],
        )
    except Exception as e:
        logger.exception("Error al consultar historial para session_id %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("Error interno al recuperar historial", e),
        )


TITLE_MAX_CHARS = 80


@router.get(
    "/sessions",
    response_model=List[SessionSummary],
    summary="Listar sesiones de chat existentes",
)
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """Lista las sesiones derivadas de `chat_messages`, ordenadas por última actividad (`updated_at` DESC)."""
    agg = await db.execute(
        select(
            ChatMessage.session_id,
            func.min(ChatMessage.created_at),
            func.max(ChatMessage.created_at),
            func.count(ChatMessage.id),
        )
        .group_by(ChatMessage.session_id)
        .order_by(func.max(ChatMessage.created_at).desc())
    )
    rows = agg.all()
    if not rows:
        return []

    first_user = await db.execute(
        select(ChatMessage.session_id, ChatMessage.content)
        .where(ChatMessage.role == "user", ChatMessage.session_id.in_([r[0] for r in rows]))
        .order_by(ChatMessage.created_at.asc())
    )
    titles: Dict[uuid.UUID, str] = {}
    for session_id, content in first_user.all():
        titles.setdefault(session_id, content[:TITLE_MAX_CHARS])

    return [
        SessionSummary(
            session_id=session_id,
            title=titles.get(session_id, ""),
            created_at=created_at,
            updated_at=updated_at,
            message_count=count,
        )
        for session_id, created_at, updated_at, count in rows
    ]


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar todos los mensajes de una sesión",
)
async def delete_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
    if not result.rowcount:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada.")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _message_dict(msg: ChatMessage) -> Dict[str, Any]:
    return {
        "role": msg.role,
        "content": msg.content,
        "created_at": msg.created_at,
        "citations": msg.citations or [],
        "executed_tools": msg.executed_tools or [],
    }


def _conversation_markdown(session_id: uuid.UUID, messages: List[Dict[str, Any]]) -> str:
    lines = [f"# Conversación {session_id}", ""]
    for msg in messages:
        label = {"user": "Usuario", "assistant": "Agente"}.get(msg["role"], msg["role"])
        lines += [f"## {label} ({msg['created_at'].isoformat()})", "", msg["content"], ""]
        if msg["citations"]:
            lines.append("**Fuentes:**")
            for cit in msg["citations"]:
                page = f", Pág {cit['page_number']}" if cit.get("page_number") else ""
                lines.append(f"- {cit.get('document_name', '?')}{page}")
            lines.append("")
        if msg["executed_tools"]:
            lines.append("**Herramientas ejecutadas:**")
            lines += [f"- `{tool.get('tool_name', '?')}`" for tool in msg["executed_tools"]]
            lines.append("")
    return "\n".join(lines)


@router.get(
    "/sessions/{session_id}/export",
    summary="Exportar una conversación completa en Markdown o PDF",
)
async def export_session(
    session_id: uuid.UUID,
    format: Literal["markdown", "pdf"] = Query("markdown"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
    )
    messages = [_message_dict(m) for m in result.scalars().all()]
    if not messages:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada.")

    if format == "pdf":
        pdf_bytes = await asyncio.to_thread(build_conversation_pdf, session_id, messages)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="session-{session_id}.pdf"'},
        )
    return Response(
        content=_conversation_markdown(session_id, messages),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="session-{session_id}.md"'},
    )


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Registrar feedback (pulgar arriba/abajo) sobre un mensaje del agente",
)
async def submit_feedback(request: FeedbackRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.id == request.message_id, ChatMessage.session_id == request.session_id
        )
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mensaje no encontrado en la sesión.")

    feedback = {
        "rating": request.rating,
        "comment": request.comment,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Reasignar un dict nuevo para que SQLAlchemy detecte el cambio en la columna JSON
    message.message_metadata = {**(message.message_metadata or {}), "feedback": feedback}
    await db.commit()

    telemetry_service.record_score(
        name="user_feedback",
        value=request.rating,
        trace_id=str(request.message_id),
        comment=request.comment,
    )
    return FeedbackResponse(message_id=request.message_id, rating=request.rating)
