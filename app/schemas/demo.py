from typing import Dict, List, Literal

from pydantic import BaseModel, Field


class DemoSeedResponse(BaseModel):
    """Resultado de la siembra idempotente del Golden Corpus."""

    documents_created: int
    documents_skipped: int
    files_created: int = Field(..., description="PDFs/PNGs generados en disco porque faltaban")
    chunks_created: int
    images_created: int
    duration_ms: float
    demo_seeded: bool


class DemoStatusResponse(BaseModel):
    """Estado actual del entorno demo."""

    db_dialect: Literal["postgresql", "sqlite"]
    demo_seeded: bool
    total_documents: int
    total_chunks: int
    total_images: int
    gemini_configured: bool
    langfuse_enabled: bool
    active_models: Dict[str, str]
    embedding_mode: Literal["gemini", "mock"] = Field(..., description="'mock' = vectores determinísticos sin API key")


class EvaluateRequest(BaseModel):
    top_k: int = Field(5, ge=1, le=20, description="Ventana k de las métricas (hit rate, MRR y NDCG)")


class QueryEvaluation(BaseModel):
    id: str
    query: str
    category: str
    hit: bool
    reciprocal_rank: float
    ndcg: float
    latency_ms: float
    relevances: List[int]
    top_documents: List[str]


class ModeEvaluation(BaseModel):
    semantic: bool = Field(..., description="False si los puntajes dependen de embeddings simulados (no semánticos)")
    hit_rate_at_k: float = Field(..., ge=0.0, le=1.0)
    mrr: float = Field(..., ge=0.0, le=1.0)
    ndcg_at_k: float = Field(..., ge=0.0, le=1.0)
    avg_latency_ms: float = Field(..., ge=0.0)
    per_query: List[QueryEvaluation]


class EvaluationResponse(BaseModel):
    top_k: int
    num_queries: int
    embedding_mode: Literal["gemini", "mock"]
    warnings: List[str] = Field(default_factory=list)
    modes: Dict[str, ModeEvaluation]
