import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.chat import ChatMessage
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    ChatHistoryResponse,
    ChatMessageResponse,
)
from app.services.agent import autonomous_agent_service

logger = logging.getLogger(__name__)

router = APIRouter()


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
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error en la ejecución del Agente IA: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno durante la ejecución del agente: {str(e)}",
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
            detail=f"Error interno al recuperar historial: {str(e)}",
        )


