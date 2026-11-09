import logging
import time
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import error_detail
from app.schemas.demo import DemoSeedResponse, DemoStatusResponse, EvaluateRequest, EvaluationResponse
from app.services.demo_seeder import get_demo_status, seed_golden_corpus
from app.services.evaluation import RAGEvaluationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/seed",
    response_model=DemoSeedResponse,
    summary="Re-siembra idempotente del Golden Corpus (3 PDFs y 3 imágenes, sin llamar a Gemini)",
)
async def seed_demo(db: AsyncSession = Depends(get_db)):
    """Genera en disco los PDFs/PNGs que falten e inserta los documentos demo que no existan."""
    started = time.perf_counter()
    try:
        result = await seed_golden_corpus(db)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.exception("Error sembrando el Golden Corpus: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("Error interno sembrando el Golden Corpus", e),
        ) from e
    return DemoSeedResponse(
        documents_created=result.documents_created,
        documents_skipped=result.documents_skipped,
        files_created=result.files_created,
        chunks_created=result.chunks_created,
        images_created=result.images_created,
        duration_ms=round((time.perf_counter() - started) * 1000.0, 1),
        demo_seeded=True,
    )


@router.get("/status", response_model=DemoStatusResponse, summary="Estado del entorno demo")
async def demo_status(db: AsyncSession = Depends(get_db)):
    return DemoStatusResponse(**await get_demo_status(db))


@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    summary="Evaluación científica RAG: dense vs sparse vs hybrid (hit rate, MRR, NDCG, latencia)",
)
async def evaluate_retrieval(
    request: EvaluateRequest | None = Body(default=None),
    lang: Literal["es", "en"] = Query("es", description="Idioma de las advertencias del informe"),
    db: AsyncSession = Depends(get_db),
):
    """Ejecuta las 8 consultas doradas en cada modalidad y devuelve métricas agregadas y por consulta."""
    if not (await get_demo_status(db))["demo_seeded"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El Golden Corpus no está sembrado. Ejecuta primero POST /api/v1/demo/seed.",
        )
    top_k = request.top_k if request else EvaluateRequest().top_k
    try:
        return await RAGEvaluationService().evaluate(db, top_k=top_k, lang=lang)
    except Exception as e:
        logger.exception("Error durante la evaluación RAG: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("Error interno durante la evaluación", e),
        ) from e
