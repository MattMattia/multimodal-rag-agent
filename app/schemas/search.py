from typing import Any, Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


SearchMode = Literal["hybrid", "dense", "sparse"]


class SearchRequest(BaseModel):
    """Solicitud de búsqueda semántica / híbrida en la base de conocimientos."""

    query: str = Field(..., min_length=1, description="Texto o consulta a buscar en los documentos")
    top_k: int = Field(5, ge=1, le=50, description="Cantidad máxima de fragmentos a recuperar")
    filter_document_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Filtrar la búsqueda a un documento específico (opcional, dejar en null o no enviar para buscar en todos)",
    )
    mode: SearchMode = Field(
        "hybrid",
        description="Modo de recuperación: 'hybrid' (vector + léxico con RRF), 'dense' (solo vector) o 'sparse' (solo BM25/léxico)",
    )
    include_parent: bool = Field(
        True,
        description="Si es True y el fragmento recuperado es hijo, incluye el contexto completo del fragmento padre",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Habilidades técnicas, lenguajes de programación y experiencia",
                "top_k": 5,
                "filter_document_id": None,
                "mode": "hybrid",
                "include_parent": True,
            }
        }
    )


class SearchResultItem(BaseModel):
    """Fragmento recuperado con métricas de relevancia y metadatos contextuales."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    content: str
    parent_id: Optional[uuid.UUID] = None
    parent_content: Optional[str] = None
    chunk_type: str = Field(..., description="'text', 'table' o 'image_description'")
    page_number: Optional[int] = None
    score: float = Field(..., description="Puntaje de relevancia unificado (RRF o similitud)")
    rank: int = Field(..., description="Posición en el orden de relevancia (iniciando en 1)")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Respuesta consolidada de búsqueda híbrida."""

    query: str
    mode: str
    total_results: int
    results: List[SearchResultItem]
