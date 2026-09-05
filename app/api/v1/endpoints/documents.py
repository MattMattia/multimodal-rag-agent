import logging
from pathlib import Path
import shutil
from typing import List, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
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

UPLOAD_DOCS_DIR = Path("uploads/documents")
UPLOAD_DOCS_DIR.mkdir(parents=True, exist_ok=True)


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
    filename = file.filename or "uploaded_file"
    file_ext = Path(filename).suffix.lower()
    content_type = file.content_type or ""

    # Validar extensión y tipo de contenido
    if file_ext not in ALLOWED_EXTENSIONS and content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Formato no soportado: '{filename}'. "
                f"Formatos admitidos: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    # Identificar tipo de archivo
    file_type = ALLOWED_MIME_TYPES.get(content_type, file_ext.replace(".", ""))

    # Generar ruta segura con UUID
    doc_id = uuid.uuid4()
    unique_filename = f"{doc_id}_{filename}"
    destination_path = UPLOAD_DOCS_DIR / unique_filename

    # Guardar en disco de forma segura
    try:
        with destination_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error("Error al guardar archivo en disco: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo guardar el archivo en el servidor: {str(e)}",
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
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con ID {document_id} no encontrado.",
        )

    # Eliminar archivo físico de disco si existe
    file_path = Path(doc.file_path)
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            logger.warning("No se pudo borrar el archivo físico %s: %s", file_path, e)

    await db.delete(doc)
    await db.commit()
    return None

