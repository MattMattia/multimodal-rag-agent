import logging
from pathlib import Path
import re
from typing import List, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import error_detail
from app.models.document import Document, DocumentChunk, DocumentImage
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentDetailResponse,
    DocumentImageResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.services.ingestion import ingestion_service

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpg",
}
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

MAGIC_SIGNATURES = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}
UPLOAD_CHUNK_SIZE = 65536

UPLOAD_DOCS_DIR = Path("uploads/documents")
UPLOAD_DOCS_DIR.mkdir(parents=True, exist_ok=True)


def _matches_magic(file_ext: str, head: bytes) -> bool:
    return any(head.startswith(sig) for sig in MAGIC_SIGNATURES.get(file_ext, ()))


def _remove_file_quietly(path: Path) -> None:
    """Borra un archivo; ignora si no existe y registra cualquier otro fallo."""
    try:
        path.unlink(missing_ok=True)
    except Exception as e:
        logger.warning("No se pudo borrar el archivo %s: %s", path, e)


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Subir documento para procesamiento multimodal",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Recibe un archivo (PDF, PNG, JPG, JPEG), lo guarda en disco, registra el documento

    y encola el pipeline de extracción multimodal (texto, tablas Markdown, diagramas con Gemini y chunks).
    """
    filename = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(file.filename or "uploaded_file").name)[:120]
    file_ext = Path(filename).suffix.lower()
    content_type = file.content_type or ""

    # Validar extensión y tipo de contenido
    if file_ext not in ALLOWED_EXTENSIONS or content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Formato no soportado: '{filename}'. "
                f"Formatos admitidos: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    # Identificar tipo de archivo
    file_type = ALLOWED_MIME_TYPES.get(content_type, file_ext.replace(".", ""))

    # Generar ruta segura con UUID y verificar contención en el directorio de documentos
    doc_id = uuid.uuid4()
    unique_filename = f"{doc_id}_{filename}"
    destination_path = UPLOAD_DOCS_DIR / unique_filename
    if not destination_path.resolve().is_relative_to(UPLOAD_DOCS_DIR.resolve()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre de archivo inválido.")

    max_bytes = int(settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024)
    total_bytes = 0
    head = b""

    # Guardar en disco por bloques, validando firma y tamaño
    try:
        with destination_path.open("wb") as buffer:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                if not head:
                    head = chunk[:16]
                    if not _matches_magic(file_ext, head):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"El contenido de '{filename}' no coincide con su extensión.",
                        )
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"El archivo supera el límite de {settings.MAX_UPLOAD_SIZE_MB:g} MB.",
                    )
                buffer.write(chunk)
        if not head:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío.")
    except HTTPException:
        _remove_file_quietly(destination_path)
        raise
    except Exception as e:
        _remove_file_quietly(destination_path)
        logger.exception("Error al guardar archivo en disco: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail("No se pudo guardar el archivo en el servidor", e),
        )
    finally:
        await file.close()

    # Guardar registro en la base de datos
    new_doc = Document(
        id=doc_id,
        filename=filename,
        file_type=file_type,
        file_path=str(destination_path),
        status="pending",
        doc_metadata={"original_name": filename, "content_type": content_type},
    )
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)

    # Encolar procesamiento en segundo plano
    background_tasks.add_task(ingestion_service.process_document_pipeline, doc_id)

    return DocumentUploadResponse(
        id=new_doc.id,
        filename=new_doc.filename,
        file_type=new_doc.file_type,
        status=new_doc.status,
        message="Archivo recibido exitosamente y encolado para extracción multimodal.",
    )


@router.get(
    "",
    response_model=List[DocumentResponse],
    summary="Listar documentos registrados",
)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Obtiene la lista paginada de documentos con métricas de fragmentos e imágenes."""
    # Subconsultas para conteos
    chunks_count_subq = (
        select(DocumentChunk.document_id, func.count(DocumentChunk.id).label("total_chunks"))
        .group_by(DocumentChunk.document_id)
        .subquery()
    )
    images_count_subq = (
        select(DocumentImage.document_id, func.count(DocumentImage.id).label("total_images"))
        .group_by(DocumentImage.document_id)
        .subquery()
    )

    query = (
        select(
            Document,
            func.coalesce(chunks_count_subq.c.total_chunks, 0).label("total_chunks"),
            func.coalesce(images_count_subq.c.total_images, 0).label("total_images"),
        )
        .outerjoin(chunks_count_subq, Document.id == chunks_count_subq.c.document_id)
        .outerjoin(images_count_subq, Document.id == images_count_subq.c.document_id)
        .order_by(Document.upload_date.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.all()

    documents_response = []
    for doc, total_chunks, total_images in rows:
        resp = DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_path=doc.file_path,
            upload_date=doc.upload_date,
            status=doc.status,
            error_message=doc.error_message,
            doc_metadata=doc.doc_metadata,
            total_chunks=total_chunks,
            total_images=total_images,
        )
        documents_response.append(resp)

    return documents_response


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Obtener detalle completo de un documento",
)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Consulta el estado, metadata, fragmentos e imágenes generadas de un documento."""
    query = (
        select(Document)
        .options(selectinload(Document.chunks), selectinload(Document.images))
        .where(Document.id == document_id)
    )
    result = await db.execute(query)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con ID {document_id} no encontrado.",
        )

    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_path=doc.file_path,
        upload_date=doc.upload_date,
        status=doc.status,
        error_message=doc.error_message,
        doc_metadata=doc.doc_metadata,
        total_chunks=len(doc.chunks),
        total_images=len(doc.images),
        chunks=[DocumentChunkResponse.model_validate(c) for c in doc.chunks],
        images=[DocumentImageResponse.model_validate(img) for img in doc.images],
    )


@router.get(
    "/{document_id}/chunks",
    response_model=List[DocumentChunkResponse],
    summary="Listar fragmentos (chunks) de un documento",
)
async def get_document_chunks(
    document_id: uuid.UUID,
    chunk_type: Optional[str] = Query(None, description="Filtrar por tipo: 'text', 'table', 'image_description'"),
    parent_only: bool = Query(False, description="Si es True, retorna solo los fragmentos padre"),
    db: AsyncSession = Depends(get_db),
):
    """Retorna los chunks extraídos para un documento con su información jerárquica."""
    query = select(DocumentChunk).where(DocumentChunk.document_id == document_id)

    if chunk_type:
        query = query.where(DocumentChunk.chunk_type == chunk_type)
    if parent_only:
        query = query.where(DocumentChunk.parent_id.is_(None))

    query = query.order_by(DocumentChunk.page_number, DocumentChunk.created_at)

    result = await db.execute(query)
    chunks = result.scalars().all()

    return [DocumentChunkResponse.model_validate(c) for c in chunks]


@router.get(
    "/{document_id}/images",
    response_model=List[DocumentImageResponse],
    summary="Listar imágenes y descripciones de Gemini de un documento",
)
async def get_document_images(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retorna las imágenes extraídas de un documento y sus descripciones generadas."""
    query = (
        select(DocumentImage)
        .where(DocumentImage.document_id == document_id)
        .order_by(DocumentImage.page_number, DocumentImage.created_at)
    )
    result = await db.execute(query)
    images = result.scalars().all()

    return [DocumentImageResponse.model_validate(img) for img in images]


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar documento y sus recursos asociados",
)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Elimina el registro de la base de datos (con chunks e imágenes en cascada) y el archivo en disco."""
    result = await db.execute(
        select(Document).options(selectinload(Document.images)).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con ID {document_id} no encontrado.",
        )

    # Eliminar archivo físico y las imágenes extraídas del disco
    _remove_file_quietly(Path(doc.file_path))
    for image in doc.images:
        _remove_file_quietly(Path(image.image_path))

    await db.delete(doc)
    await db.commit()
    return None

