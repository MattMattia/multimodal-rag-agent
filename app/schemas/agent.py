from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.search import SearchDiagnostics


class CitationItem(BaseModel):
    """Fuente o cita bibliográfica explícita utilizada en la respuesta del agente."""

    model_config = ConfigDict(from_attributes=True)

    document_name: str
    page_number: Optional[int] = None
    chunk_type: str = Field(..., description="'text', 'table' o 'image_description'")
    chunk_id: Optional[uuid.UUID] = None
    rerank_score: Optional[float] = Field(None, description="Puntaje de relevancia del Reranker Semántico")


class ToolExecutionRecord(BaseModel):
    """Registro de una herramienta invocada por el agente autónomo."""

    tool_name: str
    tool_input: Dict[str, Any] = Field(default_factory=dict)
    tool_output: Any = None
    duration_ms: Optional[float] = Field(default=None, description="Duración de la herramienta en milisegundos")
    diagnostics: Optional[SearchDiagnostics] = Field(
        default=None, description="Rayos X de latencia cuando la herramienta fue una búsqueda RAG"
    )


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
    filter_document_id: Optional[uuid.UUID] = Field(
        default=None, description="Restringe las búsquedas RAG del agente a un documento (opcional)"
    )
    search_mode: Literal["hybrid", "dense", "sparse"] = Field(
        "hybrid", description="Modo de recuperación RAG del agente"
    )
    top_k: int = Field(5, ge=1, le=50, description="Fragmentos a recuperar por búsqueda RAG")
    enable_rerank: bool = Field(True, description="Aplica reranking semántico tras la fusión RRF")
    temperature: Optional[float] = Field(
        default=None, ge=0.0, le=2.0, description="Temperatura del LLM (por defecto AGENT_TEMPERATURE)"
    )
    max_turns: Optional[int] = Field(
        default=None, ge=1, le=10, description="Máximo de iteraciones ReAct (por defecto AGENT_MAX_TURNS)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "¿Cuáles son las habilidades y experiencia de Mattia Risso? Si tiene experiencia en IA, genera un reporte en PDF.",
                "session_id": None,
                "search_mode": "hybrid",
                "top_k": 5,
                "enable_rerank": True,
            }
        }
    )

    def to_options(self) -> "AgentOptions":
        """Opciones de ejecución del agente. `top_k` solo se fija si el cliente lo envió explícitamente."""
        return AgentOptions(
            filter_document_id=self.filter_document_id,
            search_mode=self.search_mode,
            top_k=self.top_k if "top_k" in self.model_fields_set else None,
            enable_rerank=self.enable_rerank,
            temperature=self.temperature,
            max_turns=self.max_turns,
        )


@dataclass(frozen=True)
class AgentOptions:
    """Parámetros por solicitud del agente; `None` significa "usar el valor por defecto de Settings/código"."""

    filter_document_id: Optional[uuid.UUID] = None
    search_mode: str = "hybrid"
    top_k: Optional[int] = None
    enable_rerank: bool = True
    temperature: Optional[float] = None
    max_turns: Optional[int] = None


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
    diagnostics: Optional[SearchDiagnostics] = Field(
        default=None, description="Rayos X de la última búsqueda RAG del turno (si hubo alguna)"
    )
    duration_ms: Optional[float] = Field(default=None, description="Duración total del turno en milisegundos")


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



class SessionSummary(BaseModel):
    """Resumen de una sesión de chat derivado de sus mensajes."""

    session_id: uuid.UUID
    title: str = Field(..., description="Primeros 80 caracteres del primer mensaje del usuario")
    created_at: datetime
    updated_at: datetime
    message_count: int


class FeedbackRequest(BaseModel):
    """Valoración del usuario sobre un mensaje del agente."""

    session_id: uuid.UUID
    message_id: uuid.UUID
    rating: Literal[1, -1] = Field(..., description="1 = útil, -1 = no útil")
    comment: Optional[str] = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    status: str = "ok"
    message_id: uuid.UUID
    rating: int
