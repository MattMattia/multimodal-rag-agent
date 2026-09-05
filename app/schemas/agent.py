from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class CitationItem(BaseModel):
    """Fuente o cita bibliográfica explícita utilizada en la respuesta del agente."""

    model_config = ConfigDict(from_attributes=True)

    document_name: str
    page_number: Optional[int] = None
    chunk_type: str = Field(..., description="'text', 'table' o 'image_description'")
    chunk_id: Optional[uuid.UUID] = None


class ToolExecutionRecord(BaseModel):
    """Registro de una herramienta invocada por el agente autónomo."""

    tool_name: str
    tool_input: Dict[str, Any] = Field(default_factory=dict)
    tool_output: Any = None


class AgentChatRequest(BaseModel):
    """Solicitud de conversación y ejecución de tareas enviada al Agente IA."""

    message: str = Field(
        ...,
        min_length=1,
        description="Pregunta, consulta sobre documentos o instrucción de acción para el agente",
    )
    session_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Identificador único de la sesión de chat (opcional, se autogenera si no se envía)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "¿Cuáles son las habilidades y experiencia de Mattia Risso? Si tiene experiencia en IA, genera un reporte en PDF.",
                "session_id": None,
            }
        }
    )


class AgentChatResponse(BaseModel):
    """Respuesta generada por el Agente IA con trazabilidad de herramientas y citas."""

    response: str = Field(..., description="Respuesta final del agente con citas integradas")
    citations: List[CitationItem] = Field(
        default_factory=list,
        description="Lista estructurada de documentos y páginas citadas",
    )
    executed_tools: List[ToolExecutionRecord] = Field(
        default_factory=list,
        description="Lista cronológica de herramientas ejecutadas durante el turno",
    )
    session_id: uuid.UUID = Field(..., description="ID de sesión para seguimiento de conversación")


class ChatMessageResponse(BaseModel):
    """Representación de un mensaje individual en el historial de chat."""

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    citations: Optional[List[Dict[str, Any]]] = None
    executed_tools: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatHistoryResponse(BaseModel):
    """Historial completo de mensajes ordenados cronológicamente para una sesión."""

    session_id: uuid.UUID
    total_messages: int
    messages: List[ChatMessageResponse]

