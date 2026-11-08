import secrets
from pathlib import Path

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
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


def resolve_within(base: str | Path, candidate: str | Path) -> Path | None:
    """Resuelve `candidate` (ruta completa, relativa al cwd) y la devuelve solo si es un archivo existente contenido en `base`.

    Única barrera de contención de rutas para todos los endpoints que sirven archivos
    (bloquea `..`, rutas absolutas y enlaces simbólicos que escapen del directorio base).
    """
    try:
        base_resolved = Path(base).resolve()
        resolved = Path(candidate).resolve()
    except (OSError, ValueError):
        return None
    if not resolved.is_relative_to(base_resolved) or not resolved.is_file():
        return None
    return resolved
