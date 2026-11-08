import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.search import SearchRequest
from app.services.rag_search import hybrid_search_service

logger = logging.getLogger(__name__)


async def execute_search_knowledge_base(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
    mode: str = "hybrid",
    filter_document_id: uuid.UUID | None = None,
    rerank: bool = True,
) -> dict[str, Any]:
    """Ejecuta la búsqueda híbrida en el vector store y extrae contexto y citas para el Agente IA.

    Args:
        db: Sesión asíncrona de base de datos.
        query: Consulta textual a buscar.
        top_k: Cantidad de fragmentos a recuperar.
        mode: Modo ('hybrid', 'dense' o 'sparse').
        filter_document_id: ID opcional de documento para restringir la búsqueda.
        rerank: Si es True aplica reranking semántico tras la fusión.

    Returns:
        Diccionario con context_text (texto formateado para el prompt), citations, total_found y diagnostics.
    """
    logger.info("Herramienta RAG ejecutando búsqueda para: '%s' (modo: %s)", query, mode)

    request = SearchRequest(
        query=query,
        top_k=top_k,
        mode=mode,
        filter_document_id=filter_document_id,
        include_parent=True,
        rerank=rerank,
    )

    response = await hybrid_search_service.search(db=db, request=request)

    citations: list[dict[str, Any]] = []
    context_blocks: list[str] = []

    for idx, item in enumerate(response.results, start=1):
        # Guardar cita estructurada con trazabilidad de relevancia
        citations.append(
            {
                "document_name": item.document_name,
                "page_number": item.page_number,
                "chunk_type": item.chunk_type,
                "chunk_id": item.chunk_id,
                "rerank_score": item.rerank_score,
            }
        )

        # Si existe fragmento padre con mayor contexto, incorporarlo
        display_content = item.parent_content if item.parent_content else item.content
        page_str = f"Pág {item.page_number}" if item.page_number else "Sin pág"
        score_tag = f", Relevancia: {item.rerank_score:.2f}" if item.rerank_score is not None else ""

        block = (
            f"--- [Fuente #{idx}: {item.document_name} ({page_str}, Tipo: {item.chunk_type}{score_tag})] ---\n"
            f"{display_content}\n"
        )
        context_blocks.append(block)

    context_text = "\n".join(context_blocks) if context_blocks else "No se encontraron fragmentos relevantes en la base de conocimientos."

    return {
        "context_text": context_text,
        "citations": citations,
        "total_found": len(response.results),
        "diagnostics": response.diagnostics.model_dump() if response.diagnostics else None,
    }

