import secrets
from typing import Optional

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Exige el header X-API-Key cuando settings.API_KEY está configurada (vacía = acceso abierto)."""
    expected = settings.API_KEY
    if not expected:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida o ausente.",
        )


def error_detail(public_message: str, exc: Exception) -> str:
    """Mensaje para respuestas 500: solo expone la excepción si DEBUG está activo."""
    if settings.DEBUG:
        return f"{public_message}: {exc}"
    return public_message
