import logging
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.telemetry import telemetry_service
from app.models.document import Document, DocumentChunk
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem
from app.services.embedding import embedding_service
from app.services.reranker import reranker_service

logger = logging.getLogger(__name__)

MAX_RETRIEVAL_CANDIDATES = 80
SWAGGER_DUMMY_UUID = uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")


class HybridSearchService:
    """Servicio de búsqueda híbrida que combina recuperación vectorial densa (pgvector)

    con búsqueda léxica esparsa (Full-Text Search) mediante Reciprocal Rank Fusion (RRF).
    """

    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k  # Constante de suavizado estándar RRF

    async def search(self, db: AsyncSession, request: SearchRequest) -> SearchResponse:
        """Ejecuta la búsqueda según el modo seleccionado ('hybrid', 'dense' o 'sparse')."""
        query_text = request.query.strip()
        top_k = request.top_k
        doc_filter = request.filter_document_id

        # 1. Ignorar el UUID de ejemplo por defecto de Swagger UI si fue enviado sin modificar
        if doc_filter == SWAGGER_DUMMY_UUID:
            logger.info("Ignorando UUID placeholder por defecto de Swagger UI (%s)", SWAGGER_DUMMY_UUID)
            doc_filter = None

        # 2. Si se proporcionó un filter_document_id real, validar que el documento exista en la base de datos
        if doc_filter:
            doc_check = await db.execute(
                select(Document.id, Document.filename, Document.status).where(Document.id == doc_filter)
            )
            doc_row = doc_check.one_or_none()
            if not doc_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        f"El documento con filter_document_id '{doc_filter}' no existe en la base de datos. "
                        "Si deseas buscar en todos los documentos cargados, omite este campo o envíalo como null."
                    ),
                )
            if doc_row.status == "failed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El documento '{doc_row.filename}' falló durante su procesamiento y no contiene fragmentos vectorizados.",
                )

        # Instrumentación con TelemetryService (Langfuse)
        with telemetry_service.span(
            parent=None,
            name="rag_hybrid_search",
            span_type="retriever",
            input={"query": query_text, "mode": request.mode, "top_k": top_k},
            metadata={"filter_document_id": str(doc_filter) if doc_filter else None},
        ) as search_span:
            # Recuperar pool extendido para que RRF tenga suficiente solapamiento
            retrieval_limit = min(top_k * settings.SEARCH_CANDIDATE_MULTIPLIER, MAX_RETRIEVAL_CANDIDATES)

            dense_items: List[Dict[str, Any]] = []
            sparse_items: List[Dict[str, Any]] = []

            # 3. Búsqueda densa (Vectorial)
            if request.mode in ("hybrid", "dense"):
                query_vector = await embedding_service.get_embedding(query_text)
                dense_items = await self._dense_retrieval(
                    db=db,
                    query_vector=query_vector,
                    limit=retrieval_limit,
                    filter_document_id=doc_filter,
                )

            # 4. Búsqueda esparsa (Léxica Full-Text)
            if request.mode in ("hybrid", "sparse"):
                sparse_items = await self._sparse_retrieval(
                    db=db,
                    query_text=query_text,
                    limit=retrieval_limit,
                    filter_document_id=doc_filter,
                )

            # 5. Fusión y ranking según modo
            if request.mode == "dense":
                fused_candidates = dense_items
            elif request.mode == "sparse":
                fused_candidates = sparse_items
            else:  # hybrid
                fused_candidates = self._apply_rrf(dense_items, sparse_items)

            # Un único resultado por bloque padre (el de mayor puntaje) para maximizar diversidad
            fused_candidates = self._dedupe_by_parent_block(fused_candidates)

            # Si se solicita reranking semántico (por defecto True):
            # Tomar una ventana más amplia de candidatos (top_k * 3) y pasarlos por RerankerService
            if getattr(request, "rerank", True) and fused_candidates:
                candidate_window = fused_candidates[: top_k * 3]
                final_ranked = await reranker_service.rerank(
                    query=query_text,
                    candidates=candidate_window,
                    top_n=top_k,
                )
            else:
                final_ranked = fused_candidates[:top_k]

            # 6. Enriquecimiento jerárquico con Parent-Document Context
            if request.include_parent:
                await self.attach_parent_context(db=db, ranked_items=final_ranked)

            # 7. Mapear a respuesta Pydantic
            results = []
            for rank, item in enumerate(final_ranked, start=1):
                raw_rerank = item.get("rerank_score")
                results.append(
                    SearchResultItem(
                        chunk_id=item["chunk_id"],
                        document_id=item["document_id"],
                        document_name=item["document_name"],
                        content=item["content"],
                        parent_id=item.get("parent_id"),
                        parent_content=item.get("parent_content"),
                        chunk_type=item["chunk_type"],
                        page_number=item.get("page_number"),
                        score=round(float(item["score"]), 6),
                        rerank_score=round(float(raw_rerank), 4) if raw_rerank is not None else None,
                        rank=rank,
                        metadata=item.get("metadata", {}),
                    )
                )

            if hasattr(search_span, "update"):
                search_span.update(output={"total_results": len(results), "mode": request.mode})

        return SearchResponse(
            query=request.query,
            mode=request.mode,
            total_results=len(results),
            results=results,
        )

    async def _dense_retrieval(
        self,
        db: AsyncSession,
        query_vector: List[float],
        limit: int,
        filter_document_id: Optional[uuid.UUID],
    ) -> List[Dict[str, Any]]:
        """Búsqueda vectorial densa por distancia de coseno en pgvector."""
        distance_expr = DocumentChunk.embedding.cosine_distance(query_vector)

        stmt = (
            select(DocumentChunk, Document.filename, distance_expr.label("distance"))
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.embedding.is_not(None))
        )

        if filter_document_id:
            stmt = stmt.where(DocumentChunk.document_id == filter_document_id)

        stmt = stmt.order_by(distance_expr.asc()).limit(limit)

        result = await db.execute(stmt)
        rows = result.all()

        ranked = []
        for chunk, filename, distance in rows:
            dist_val = float(distance) if distance is not None else 1.0
            # Similitud de coseno: 1 - distancia
            similarity = max(0.0, min(1.0, 1.0 - dist_val))
            ranked.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "document_name": filename,
                    "content": chunk.content,
                    "parent_id": chunk.parent_id,
                    "chunk_type": chunk.chunk_type,
                    "page_number": chunk.page_number,
                    "score": similarity,
                    "metadata": chunk.chunk_metadata,
                }
            )

        return ranked

    async def _sparse_retrieval(
        self,
        db: AsyncSession,
        query_text: str,
        limit: int,
        filter_document_id: Optional[uuid.UUID],
    ) -> List[Dict[str, Any]]:
        """Búsqueda léxica esparsa con soporte bilingüe (español e inglés) y fallback por tokens."""
        # Configuración de diccionarios en español e inglés
        # La configuración se emite como literal SQL (no parámetro) para que la expresión
        # to_tsvector('<cfg>', content) coincida exactamente con los índices GIN.
        cfg_es = literal_column("'spanish'")
        cfg_en = literal_column("'english'")
        ts_query_es = func.websearch_to_tsquery(cfg_es, query_text)
        ts_query_en = func.websearch_to_tsquery(cfg_en, query_text)
        ts_vector_es = func.to_tsvector(cfg_es, DocumentChunk.content)
        ts_vector_en = func.to_tsvector(cfg_en, DocumentChunk.content)

        rank_expr = func.greatest(
            func.ts_rank_cd(ts_vector_es, ts_query_es),
            func.ts_rank_cd(ts_vector_en, ts_query_en),
        ).label("rank")

        match_cond = or_(
            ts_vector_es.op("@@")(ts_query_es),
            ts_vector_en.op("@@")(ts_query_en),
        )

        stmt = (
            select(DocumentChunk, Document.filename, rank_expr)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(match_cond)
        )

        if filter_document_id:
            stmt = stmt.where(DocumentChunk.document_id == filter_document_id)

        stmt = stmt.order_by(rank_expr.desc()).limit(limit)
        result = await db.execute(stmt)
        rows = result.all()

        # 2. Fallback con ILIKE por tokens si los analizadores de lenguaje no arrojaron coincidencias directas
        if not rows:
            clean_tokens = [
                t.strip(" '\".,;:()[]{}")
                for t in query_text.split()
                if len(t.strip(" '\".,;:()[]{}")) > 2
            ]
            if clean_tokens:
                ilike_filters = [DocumentChunk.content.ilike(f"%{t}%") for t in clean_tokens[:6]]
                stmt_fallback = (
                    select(DocumentChunk, Document.filename)
                    .join(Document, DocumentChunk.document_id == Document.id)
                    .where(or_(*ilike_filters))
                )
                if filter_document_id:
                    stmt_fallback = stmt_fallback.where(DocumentChunk.document_id == filter_document_id)
                stmt_fallback = stmt_fallback.limit(limit)
                fallback_result = await db.execute(stmt_fallback)
                rows = [(chunk, fname, 0.05) for chunk, fname in fallback_result.all()]

        ranked = []
        for chunk, filename, rank_val in rows:
            score = float(rank_val) if rank_val is not None else 0.0
            ranked.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "document_name": filename,
                    "content": chunk.content,
                    "parent_id": chunk.parent_id,
                    "chunk_type": chunk.chunk_type,
                    "page_number": chunk.page_number,
                    "score": score,
                    "metadata": chunk.chunk_metadata,
                }
            )

        return ranked

    def _apply_rrf(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Combina rankings densos y esparsos calculando el puntaje unificado RRF:

        RRF(d) = sum( 1 / (k + rank_i) )
        """
        scores: Dict[uuid.UUID, float] = {}
        items_map: Dict[uuid.UUID, Dict[str, Any]] = {}

        # Procesar lista densa
        for rank, item in enumerate(dense_results, start=1):
            c_id = item["chunk_id"]
            items_map[c_id] = item
            rrf_val = 1.0 / (self.rrf_k + rank)
            scores[c_id] = scores.get(c_id, 0.0) + rrf_val

        # Procesar lista esparsa
        for rank, item in enumerate(sparse_results, start=1):
            c_id = item["chunk_id"]
            if c_id not in items_map:
                items_map[c_id] = item
            rrf_val = 1.0 / (self.rrf_k + rank)
            scores[c_id] = scores.get(c_id, 0.0) + rrf_val

        # Ordenar de mayor a menor RRF
        sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

        fused_items = []
        for cid in sorted_ids:
            merged_item = dict(items_map[cid])
            merged_item["score"] = scores[cid]
            fused_items.append(merged_item)

        return fused_items

    @staticmethod
    def _dedupe_by_parent_block(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Conserva el primer (mejor puntuado) candidato de cada bloque efectivo (parent_id o chunk_id)."""
        seen: set = set()
        unique: List[Dict[str, Any]] = []
        for item in items:
            block_id = item.get("parent_id") or item["chunk_id"]
            if block_id in seen:
                continue
            seen.add(block_id)
            unique.append(item)
        return unique

    async def attach_parent_context(
        self, db: AsyncSession, ranked_items: List[Dict[str, Any]]
    ) -> None:
        """Carga en una sola consulta el contenido del fragmento padre (Parent-Document Retrieval)."""
        parent_ids = {
            item["parent_id"]
            for item in ranked_items
            if item.get("parent_id") is not None
        }

        if not parent_ids:
            return

        stmt = select(DocumentChunk.id, DocumentChunk.content).where(
            DocumentChunk.id.in_(parent_ids)
        )
        result = await db.execute(stmt)
        parent_map = {p_id: content for p_id, content in result.all()}

        for item in ranked_items:
            p_id = item.get("parent_id")
            if p_id and p_id in parent_map:
                item["parent_content"] = parent_map[p_id]

    _attach_parent_context = attach_parent_context


hybrid_search_service = HybridSearchService()
