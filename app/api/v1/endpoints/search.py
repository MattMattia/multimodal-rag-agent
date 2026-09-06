import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.search import SearchRequest, SearchResponse
from app.services.rag_search import hybrid_search_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=SearchResponse,
    summary="Búsqueda híbrida en la base de conocimientos RAG",
)
async def search_knowledge_base(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ejecuta una búsqueda semántica e híbrida en los documentos vectorizados con Reranking Semántico.

    - **hybrid**: Combina búsqueda densa por similitud de coseno en pgvector y búsqueda léxica (PostgreSQL ts_rank) usando Reciprocal Rank Fusion (RRF).
    - **dense**: Búsqueda exclusivamente por similitud de embeddings vectoriales.
    - **sparse**: Búsqueda exclusivamente léxica por palabras clave y concordancia textual (soporte bilingüe español e inglés).
    - **rerank**: Si es True (por defecto), reevalúa y reordena los candidatos mediante `RerankerService` con Gemini, retornando `rerank_score`.
    - **include_parent**: Cuando el fragmento coincidente es un fragmento hijo, incluye el contexto completo del bloque padre para el LLM.
    - **filter_document_id**: Opcional. Permite limitar la búsqueda a un documento específico (en Swagger UI se muestra como null por defecto).
    """
    try:
        response = await hybrid_search_service.search(db=db, request=request)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error al ejecutar búsqueda híbrida: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno durante la búsqueda: {str(e)}",
        )
