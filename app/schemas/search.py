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
    rerank: bool = Field(
        True,
        description="Si es True, aplica una etapa de Reranking Semántico con Gemini posterior a la fusión RRF",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Habilidades técnicas, lenguajes de programación y experiencia",
                "top_k": 5,
                "filter_document_id": None,
                "mode": "hybrid",
                "include_parent": True,
                "rerank": True,
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
    rerank_score: Optional[float] = Field(None, description="Puntaje de relevancia refinado por el Reranker Semántico (0.0 - 1.0)")
    rank: int = Field(..., description="Posición en el orden de relevancia (iniciando en 1)")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchDiagnostics(BaseModel):
    """Rayos X de latencia: tiempo (ms) de cada etapa de `HybridSearchService.search`."""

    db_dialect: str = Field(..., description="Dialecto de la base de datos activa: 'postgresql' o 'sqlite'")
    embedding_ms: float = Field(..., description="Generación del embedding de la consulta (0 si el modo es 'sparse')")
    dense_ms: float = Field(..., description="Recuperación vectorial densa (0 si el modo es 'sparse')")
    sparse_ms: float = Field(..., description="Recuperación léxica esparsa (0 si el modo es 'dense')")
    rrf_fusion_ms: float = Field(..., description="Fusión RRF y deduplicación por bloque padre")
    rerank_ms: float = Field(..., description="Reranking semántico (0 si está desactivado)")
    total_ms: float = Field(..., description="Duración total de la búsqueda")
    raw_candidates_count: int = Field(..., description="Candidatos tras la fusión, antes de deduplicar")
    deduped_blocks_count: int = Field(..., description="Bloques únicos tras deduplicar por fragmento padre")


class SearchResponse(BaseModel):
    """Respuesta consolidada de búsqueda híbrida."""

    query: str
    mode: str
    total_results: int
    results: List[SearchResultItem]
    diagnostics: Optional[SearchDiagnostics] = Field(
        default=None, description="Latencia por etapa (rayos X) de esta búsqueda"
    )
