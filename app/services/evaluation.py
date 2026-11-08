"""Suite de evaluación RAG: compara recuperación densa, esparsa e híbrida (RRF + reranker) sobre el Golden Corpus.

Relevancia binaria: un resultado es relevante si pertenece a un documento esperado y su contenido (o el de su
bloque padre) contiene al menos una palabra clave esperada. Las métricas usan las fórmulas estándar de IR.
"""

import math
import time
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.schemas.search import SearchRequest
from app.services.rag_search import HybridSearchService, hybrid_search_service

MODES = ("dense", "sparse", "hybrid")

GOLDEN_EVAL_QUERIES: List[Dict[str, Any]] = [
    {
        "id": "q1",
        "category": "text",
        "query": "¿Qué parámetros usa el índice HNSW?",
        "expected_doc_filenames": ["Arquitectura_Cloud_IA_2026.pdf"],
        "expected_keywords": ["m=16", "ef_construction=64"],
    },
    {
        "id": "q2",
        "category": "text",
        "query": "¿Cuál es la constante k de la fusión Reciprocal Rank Fusion RRF?",
        "expected_doc_filenames": ["Arquitectura_Cloud_IA_2026.pdf"],
        "expected_keywords": ["k=60"],
    },
    {
        "id": "q3",
        "category": "table",
        "query": "how long does the reranking step take in the slowest 5% of requests?",
        "expected_doc_filenames": ["Arquitectura_Cloud_IA_2026.pdf"],
        "expected_keywords": ["310"],
    },
    {
        "id": "q4",
        "category": "table",
        "query": "¿Cuánto fueron los ingresos de Norteamérica en el trimestre?",
        "expected_doc_filenames": ["Reporte_Financiero_Q3_GlobalTech.pdf"],
        "expected_keywords": ["$45M"],
    },
    {
        "id": "q5",
        "category": "table",
        "query": "ganancia operativa porcentual",
        "expected_doc_filenames": ["Reporte_Financiero_Q3_GlobalTech.pdf"],
        "expected_keywords": ["34%"],
    },
    {
        "id": "q6",
        "category": "security",
        "query": "¿Cómo evitan que un webhook apunte a IPs internas?",
        "expected_doc_filenames": ["Manual_Seguridad_ZeroTrust_OWASP.pdf"],
        "expected_keywords": ["SSRF", "allow-list"],
    },
    {
        "id": "q7",
        "category": "security",
        "query": "What safeguards protect the files that users upload?",
        "expected_doc_filenames": ["Manual_Seguridad_ZeroTrust_OWASP.pdf"],
        "expected_keywords": ["magic bytes", "MAX_UPLOAD_SIZE_MB"],
    },
    {
        "id": "q8",
        "category": "diagram",
        "query": "esquema visual de cómo se conectan los servicios con la base de datos",
        "expected_doc_filenames": ["Arquitectura_Cloud_IA_2026.pdf"],
        "expected_keywords": ["diagrama"],
    },
]


# --- métricas (relevancias binarias en orden de ranking) -------------------------------------------------
def hit_rate_at_k(relevances: Sequence[int], k: int) -> float:
    """1.0 si hay al menos un resultado relevante entre los k primeros; si no, 0.0."""
    return 1.0 if any(relevances[:k]) else 0.0


def reciprocal_rank(relevances: Sequence[int], k: Optional[int] = None) -> float:
    """1 / posición del primer resultado relevante (0.0 si no hay ninguno en la ventana)."""
    window = relevances if k is None else relevances[:k]
    for position, relevant in enumerate(window, start=1):
        if relevant:
            return 1.0 / position
    return 0.0


def _dcg(relevances: Sequence[int]) -> float:
    return sum(rel / math.log2(position + 1) for position, rel in enumerate(relevances, start=1))


def ndcg_at_k(relevances: Sequence[int], k: int, total_relevant: Optional[int] = None) -> float:
    """NDCG@k = DCG@k / IDCG@k, con DCG = suma de rel_i / log2(i + 1).

    IDCG supone min(k, total_relevant) resultados relevantes en las primeras posiciones, donde `total_relevant` es
    cuántos ítems relevantes existen en el corpus (así NDCG refleja el recall). Sin ese dato se reordena la lista
    recuperada.
    """
    if total_relevant is None:
        ideal = _dcg(sorted(relevances, reverse=True)[:k])
    else:
        ideal = _dcg([1] * min(k, total_relevant))
    if ideal == 0.0:
        return 0.0
    return _dcg(relevances[:k]) / ideal


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def is_relevant(result: Dict[str, Any], expected_docs: Sequence[str], expected_keywords: Sequence[str]) -> bool:
    """Documento esperado y, si hay palabras clave, al menos una presente en el contenido o en el del padre."""
    if result.get("document_name") not in expected_docs:
        return False
    if not expected_keywords:
        return True
    haystack = f"{result.get('content') or ''} {result.get('parent_content') or ''}".lower()
    return any(keyword.lower() in haystack for keyword in expected_keywords)


class RAGEvaluationService:
    """Ejecuta GOLDEN_EVAL_QUERIES en cada modalidad y agrega hit rate, MRR, NDCG y latencia."""

    def __init__(self, search_service: Optional[HybridSearchService] = None, queries: Optional[List[Dict[str, Any]]] = None):
        self.search_service = search_service or hybrid_search_service
        self.queries = queries if queries is not None else GOLDEN_EVAL_QUERIES

    async def evaluate(self, db: AsyncSession, top_k: int = 5, modes: Sequence[str] = MODES) -> Dict[str, Any]:
        from app.services.demo_seeder import gemini_configured

        embedding_mode = "gemini" if gemini_configured() else "mock"
        report: Dict[str, Any] = {
            "top_k": top_k,
            "num_queries": len(self.queries),
            "embedding_mode": embedding_mode,
            "warnings": [],
            "modes": {},
        }
        if embedding_mode == "mock":
            report["warnings"].append(
                "Embeddings simulados: los puntajes de dense y hybrid provienen de vectores determinísticos SHA-256 "
                "(mock) y no miden calidad semántica; solo sparse (BM25) es significativo sin GOOGLE_API_KEY."
            )
        totals = [await self._count_relevant_blocks(db, spec) for spec in self.queries]
        for mode in modes:
            rows = [
                await self._run_query(db, spec, mode, top_k, total)
                for spec, total in zip(self.queries, totals)
            ]
            report["modes"][mode] = {
                "semantic": mode == "sparse" or embedding_mode == "gemini",
                "hit_rate_at_k": mean([1.0 if row["hit"] else 0.0 for row in rows]),
                "mrr": mean([row["reciprocal_rank"] for row in rows]),
                "ndcg_at_k": mean([row["ndcg"] for row in rows]),
                "avg_latency_ms": mean([row["latency_ms"] for row in rows]),
                "per_query": rows,
            }
        return report

    @staticmethod
    async def _count_relevant_blocks(db: AsyncSession, spec: Dict[str, Any]) -> int:
        """Bloques (padre o chunk suelto) del corpus que cumplen la misma regla de relevancia que los resultados."""
        stmt = (
            select(DocumentChunk.id, DocumentChunk.parent_id, DocumentChunk.content, Document.filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.filename.in_(spec["expected_doc_filenames"]))
        )
        rows = (await db.execute(stmt)).all()
        content_by_id = {row.id: row.content for row in rows}
        blocks = set()
        for row in rows:
            parent_content = content_by_id.get(row.parent_id) if row.parent_id else None
            result = {"document_name": row.filename, "content": row.content, "parent_content": parent_content}
            if is_relevant(result, spec["expected_doc_filenames"], spec["expected_keywords"]):
                blocks.add(row.parent_id or row.id)
        return len(blocks)

    async def _run_query(
        self, db: AsyncSession, spec: Dict[str, Any], mode: str, top_k: int, total_relevant: Optional[int] = None
    ) -> Dict[str, Any]:
        # La modalidad híbrida incluye RRF + reranker; dense y sparse se miden "puras".
        request = SearchRequest(query=spec["query"], top_k=top_k, mode=mode, rerank=(mode == "hybrid"), include_parent=True)
        started = time.perf_counter()
        response = await self.search_service.search(db=db, request=request)
        latency_ms = (time.perf_counter() - started) * 1000.0

        relevances = [
            1 if is_relevant(item.model_dump(), spec["expected_doc_filenames"], spec["expected_keywords"]) else 0
            for item in response.results
        ]
        return {
            "id": spec["id"],
            "query": spec["query"],
            "category": spec["category"],
            "hit": bool(hit_rate_at_k(relevances, top_k)),
            "reciprocal_rank": reciprocal_rank(relevances, top_k),
            "ndcg": ndcg_at_k(relevances, top_k, total_relevant),
            "latency_ms": round(latency_ms, 3),
            "relevances": relevances,
            "top_documents": [item.document_name for item in response.results],
        }
