"""Endpoints autenticados para servir archivos: reportes PDF, documentos originales e imágenes extraídas."""

from pathlib import Path
from typing import Iterable, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import resolve_within
from app.models.document import Document, DocumentImage

router = APIRouter()

REPORTS_DIR = Path("uploads/reports")
DOCUMENTS_DIR = Path("uploads/documents")
IMAGES_DIR = Path("uploads/images")

IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
DOCUMENT_MIME_TYPES = {
    ".pdf": "application/pdf",
    **IMAGE_MIME_TYPES,
}


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def report_response(base_dir: Path, filename: str) -> FileResponse:
    """Sirve un PDF de `base_dir` (inline) validando contención de ruta; 404 en cualquier otro caso."""
    candidate = resolve_within(base_dir, Path(base_dir) / filename)
    if candidate is None or candidate.suffix.lower() != ".pdf":
        raise _not_found("Reporte no encontrado.")
    return FileResponse(
        candidate,
        media_type="application/pdf",
        filename=candidate.name,
        content_disposition_type="inline",
    )


def _stored_file_response(
    stored_path: str, allowed_dirs: Iterable[Path], mime_types: dict, detail: str
) -> FileResponse:
    for base in allowed_dirs:
        resolved = resolve_within(base, stored_path)
        if resolved is None:
            continue
        mime: Optional[str] = mime_types.get(resolved.suffix.lower())
        if mime is None:
            break
        return FileResponse(resolved, media_type=mime)
    raise _not_found(detail)


@router.get("/reports/{filename}", summary="Descargar un reporte PDF generado por el agente")
async def get_report(filename: str):
    return report_response(REPORTS_DIR, filename)


@router.get("/documents/{document_id}/file", summary="Descargar el archivo original subido")
async def get_document_file(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document.file_path).where(Document.id == document_id))
    file_path = result.scalar_one_or_none()
    if file_path is None:
        raise _not_found("Documento no encontrado.")
    return _stored_file_response(file_path, [DOCUMENTS_DIR], DOCUMENT_MIME_TYPES, "Archivo no encontrado.")


@router.get(
    "/documents/{document_id}/images/{image_id}/file",
    summary="Descargar una imagen extraída de un documento",
)
async def get_document_image_file(
    document_id: uuid.UUID, image_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(DocumentImage.image_path).where(
            DocumentImage.id == image_id, DocumentImage.document_id == document_id
        )
    )
    image_path = result.scalar_one_or_none()
    if image_path is None:
        raise _not_found("Imagen no encontrada.")
    # Las imágenes sueltas subidas por el usuario viven en uploads/documents; las extraídas de PDFs en uploads/images.
    return _stored_file_response(
        image_path, [IMAGES_DIR, DOCUMENTS_DIR], IMAGE_MIME_TYPES, "Archivo de imagen no encontrado."
    )
