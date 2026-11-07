import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Verificación del estado del sistema y la base de datos")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Verifica el estado operativo del servicio y la conectividad con PostgreSQL y la extensión pgvector."""
    db_status = "connected"
    try:
        # Verificar conectividad básica y presencia de la extensión pgvector
        result = await db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector';"))
        vector_installed = result.scalar_one_or_none() is not None
        if vector_installed:
            db_status = "connected (pgvector active)"
        else:
            db_status = "connected (pgvector not found)"
    except Exception as e:
        logger.exception("Health check: base de datos inalcanzable: %s", e)
        db_status = f"unreachable: {e}" if settings.DEBUG else "unreachable"

    overall_status = "ok" if "connected" in db_status else "degraded"

    return HealthResponse(
        status=overall_status,
        project=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        database=db_status,
    )

