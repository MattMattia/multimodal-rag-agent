import asyncio
import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

from PIL import Image
import pdfplumber
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.document import Document, DocumentChunk, DocumentImage
from app.services.embedding import embedding_service
from app.services.vision import vision_service

logger = logging.getLogger(__name__)

# Fallback si langchain_text_splitters no está instalado directamente en local
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    class RecursiveCharacterTextSplitter:
        """Divisor de texto de respaldo simple en caso de no tener langchain_text_splitters."""
        def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100, separators: Optional[List[str]] = None):
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap

        def split_text(self, text: str) -> List[str]:
            if not text:
                return []
            chunks = []
            start = 0
            while start < len(text):
                end = start + self.chunk_size
                chunks.append(text[start:end])
                start += self.chunk_size - self.chunk_overlap
            return chunks


def table_to_markdown(table: List[List[Optional[str]]]) -> str:
    """Convierte una matriz bidimensional de celdas (extraída con pdfplumber) a tabla Markdown."""
    if not table or not any(table):
        return ""

    # Limpiar y normalizar celdas
    cleaned_table = []
    for row in table:
        cleaned_row = []
        for cell in row:
            if cell is None:
                cleaned_row.append("")
            else:
                # Reemplazar saltos de línea internos por espacios para no romper la fila Markdown
                cell_str = str(cell).replace("\n", " ").strip()
                # Escapar barras verticales
                cell_str = cell_str.replace("|", "\\|")
                cleaned_row.append(cell_str)
        cleaned_table.append(cleaned_row)

    if not cleaned_table:
        return ""

    num_cols = max(len(row) for row in cleaned_table)
    # Rellenar filas cortas si existieran
    for row in cleaned_table:
        while len(row) < num_cols:
            row.append("")

    header = cleaned_table[0]
    separator = ["---"] * num_cols

    markdown_lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]

    for row in cleaned_table[1:]:
        markdown_lines.append("| " + " | ".join(row) + " |")

    return "\n".join(markdown_lines)


class IngestionService:
    """Servicio para procesar documentos multimodalmente (PDFs, imágenes, tablas y chunks jerárquicos)."""

    def __init__(
        self,
        parent_chunk_size: int = 1200,
        parent_chunk_overlap: int = 120,
        child_chunk_size: int = 350,
        child_chunk_overlap: int = 40,
    ):
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_chunk_size,
            chunk_overlap=parent_chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_chunk_size,
            chunk_overlap=child_chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    async def process_document_pipeline(self, document_id: uuid.UUID) -> None:
        """Punto de entrada asíncrono para ejecutar la ingesta de un documento en background."""
        logger.info("Iniciando pipeline de ingesta para documento ID: %s", document_id)

        async with AsyncSessionLocal() as db:
            # 1. Obtener registro del documento
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if not doc:
                logger.error("Documento %s no encontrado en la base de datos.", document_id)
                return

            # 2. Actualizar estado a 'processing'
            doc.status = "processing"
            await db.commit()

            try:
                file_path = Path(doc.file_path)
                if not file_path.exists():
                    raise FileNotFoundError(f"El archivo {doc.file_path} no existe en disco.")

                file_type = doc.file_type.lower()
                total_chunks = 0
                total_images = 0
                metadata_summary: Dict[str, Any] = {}

                # 3. Procesamiento según tipo de archivo
                if "pdf" in file_type or file_path.suffix.lower() == ".pdf":
                    total_chunks, total_images, metadata_summary = await self._process_pdf(
                        db=db, doc=doc, file_path=file_path
                    )
                elif any(ext in file_type for ext in ["image", "png", "jpeg", "jpg"]):
                    total_chunks, total_images, metadata_summary = await self._process_standalone_image(
                        db=db, doc=doc, file_path=file_path
                    )
                else:
                    raise ValueError(f"Tipo de archivo no soportado para ingesta: {doc.file_type}")

                # 4. Generar y almacenar embeddings vectoriales para todos los chunks
                chunks_res = await db.execute(
                    select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
                )
                chunks_to_embed = chunks_res.scalars().all()
                if chunks_to_embed:
                    logger.info("Generando embeddings para %d fragmentos...", len(chunks_to_embed))
                    texts = [c.content for c in chunks_to_embed]
                    vectors = await embedding_service.get_embeddings_batch(texts, batch_size=50)
                    for chunk, vector in zip(chunks_to_embed, vectors):
                        chunk.embedding = vector
                    await db.flush()

                # 5. Finalización exitosa
                doc.status = "completed"
                doc.error_message = None
                doc.doc_metadata = {
                    **doc.doc_metadata,
                    **metadata_summary,
                    "total_chunks": total_chunks,
                    "total_images": total_images,
                }
                await db.commit()
                logger.info(
                    "Ingesta completada exitosamente para documento %s. Chunks: %d, Imágenes: %d",
                    document_id,
                    total_chunks,
                    total_images,
                )

            except Exception as e:
                err_str = str(e)
                logger.exception("Error crítico durante la ingesta del documento %s: %s", document_id, err_str)
                try:
                    await db.rollback()
                    from sqlalchemy import update
                    await db.execute(
                        update(Document)
                        .where(Document.id == document_id)
                        .values(status="failed", error_message=err_str)
                    )
                    await db.commit()
                except Exception as rollback_err:
                    logger.error("Error al persistir estado fallido en BD para %s: %s", document_id, rollback_err)

    async def _process_pdf(
        self, db: AsyncSession, doc: Document, file_path: Path
    ) -> Tuple[int, int, Dict[str, Any]]:
        """Extrae texto, tablas e imágenes de un archivo PDF y genera chunks jerárquicos."""
        total_chunks = 0
        total_images = 0
        total_tables = 0

        images_output_dir = Path("uploads/images")
        images_output_dir.mkdir(parents=True, exist_ok=True)

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

            for page_idx, page in enumerate(pdf.pages, start=1):
                page_text_elements: List[str] = []

                # --- A. Extracción de Tablas ---
                tables = page.extract_tables() or []
                for t_idx, table in enumerate(tables, start=1):
                    md_table = table_to_markdown(table)
                    if md_table:
                        total_tables += 1
                        table_content = f"### [Tabla Página {page_idx} - Ítem {t_idx}]\n{md_table}"
                        page_text_elements.append(table_content)

                        # Guardar tabla como chunk especializado
                        table_chunk = DocumentChunk(
                            document_id=doc.id,
                            parent_id=None,
                            content=table_content,
                            chunk_type="table",
                            page_number=page_idx,
                            chunk_metadata={"table_index": t_idx, "level": "parent"},
                        )
                        db.add(table_chunk)
                        await db.flush()
                        total_chunks += 1

                # --- B. Extracción de Imágenes embebidas ---
                page_images = page.images or []
                for img_idx, img_meta in enumerate(page_images, start=1):
                    try:
                        # Extraer bounding box de la imagen si está disponible
                        x0 = img_meta.get("x0", 0)
                        top = img_meta.get("top", 0)
                        x1 = img_meta.get("x1", page.width)
                        bottom = img_meta.get("bottom", page.height)

                        # Validar dimensiones mínimas razonables (filtrar pequeños iconos decorativos)
                        if (x1 - x0) > 40 and (bottom - top) > 40:
                            cropped_page = page.crop((x0, top, x1, bottom))
                            img_obj = cropped_page.to_image(resolution=150)

                            img_filename = f"{doc.id}_p{page_idx}_img{img_idx}.png"
                            saved_img_path = images_output_dir / img_filename
                            img_obj.save(str(saved_img_path), format="PNG")

                            # Descripción técnica con Gemini 1.5 Flash
                            description = await vision_service.describe_image(
                                str(saved_img_path), prompt_type="technical"
                            )

                            doc_image = DocumentImage(
                                document_id=doc.id,
                                image_path=str(saved_img_path),
                                description=description,
                                page_number=page_idx,
                                image_metadata={"image_index": img_idx, "bbox": [x0, top, x1, bottom]},
                            )
                            db.add(doc_image)
                            total_images += 1

                            # Generar chunk semántico para búsqueda RAG
                            img_chunk_content = (
                                f"### [Imagen/Diagrama Técnico - Página {page_idx}]\n"
                                f"Archivo: {img_filename}\n"
                                f"Descripción del gráfico: {description}"
                            )
                            img_chunk = DocumentChunk(
                                document_id=doc.id,
                                parent_id=None,
                                content=img_chunk_content,
                                chunk_type="image_description",
                                page_number=page_idx,
                                chunk_metadata={"image_path": str(saved_img_path), "level": "parent"},
                            )
                            db.add(img_chunk)
                            await db.flush()
                            total_chunks += 1

                    except Exception as img_err:
                        logger.warning(
                            "No se pudo extraer imagen %d en pág %d de %s: %s",
                            img_idx,
                            page_idx,
                            doc.filename,
                            img_err,
                        )

                # --- C. Extracción de Texto y Chunking Jerárquico ---
                extracted_text = page.extract_text() or ""
                if extracted_text.strip():
                    cleaned_text = (
                        extracted_text.replace("\uf0b7", "- ")
                        .replace("\u2022", "- ")
                        .replace("\ufffd", "")
                    )
                    page_text_elements.append(cleaned_text)

                combined_page_text = "\n\n".join(page_text_elements)
                if combined_page_text.strip():
                    # Crear chunks padre (Parent Chunks)
                    parent_texts = self.parent_splitter.split_text(combined_page_text)
                    for p_idx, p_text in enumerate(parent_texts):
                        parent_chunk = DocumentChunk(
                            document_id=doc.id,
                            parent_id=None,
                            content=p_text,
                            chunk_type="text",
                            page_number=page_idx,
                            chunk_metadata={"parent_index": p_idx, "level": "parent"},
                        )
                        db.add(parent_chunk)
                        await db.flush()  # Para obtener parent_chunk.id
                        total_chunks += 1

                        # Crear sub-chunks hijos (Child Chunks) vinculados al padre
                        child_texts = self.child_splitter.split_text(p_text)
                        # Solo crear hijos si el texto se dividió en más de 1 parte
                        if len(child_texts) > 1:
                            for c_idx, c_text in enumerate(child_texts):
                                child_chunk = DocumentChunk(
                                    document_id=doc.id,
                                    parent_id=parent_chunk.id,
                                    content=c_text,
                                    chunk_type="text",
                                    page_number=page_idx,
                                    chunk_metadata={
                                        "parent_index": p_idx,
                                        "child_index": c_idx,
                                        "level": "child",
                                    },
                                )
                                db.add(child_chunk)
                                total_chunks += 1

            await db.commit()

        return total_chunks, total_images, {
            "total_pages": total_pages,
            "total_tables": total_tables,
        }

    async def _process_standalone_image(
        self, db: AsyncSession, doc: Document, file_path: Path
    ) -> Tuple[int, int, Dict[str, Any]]:
        """Procesa una imagen directa (factura, recibo, diagrama) usando Gemini 1.5 Flash."""
        total_chunks = 0
        total_images = 1

        # Determinar el tipo de prompt según nombre o metadata
        is_receipt = any(k in doc.filename.lower() for k in ["factura", "recibo", "invoice", "ticket", "boleta"])
        prompt_type = "receipt" if is_receipt else "technical"

        # Generar análisis exhaustivo con Gemini
        description = await vision_service.describe_image(str(file_path), prompt_type=prompt_type)

        doc_image = DocumentImage(
            document_id=doc.id,
            image_path=str(file_path),
            description=description,
            page_number=1,
            image_metadata={"prompt_type": prompt_type, "original_filename": doc.filename},
        )
        db.add(doc_image)

        # Chunking jerárquico de la descripción generada
        parent_texts = self.parent_splitter.split_text(description)
        for p_idx, p_text in enumerate(parent_texts):
            prefix = f"### [Documento Visual: {doc.filename}]\n" if p_idx == 0 else ""
            parent_chunk = DocumentChunk(
                document_id=doc.id,
                parent_id=None,
                content=f"{prefix}{p_text}",
                chunk_type="image_description",
                page_number=1,
                chunk_metadata={"parent_index": p_idx, "level": "parent", "is_receipt": is_receipt},
            )
            db.add(parent_chunk)
            await db.flush()
            total_chunks += 1

            # Sub-chunks hijos
            child_texts = self.child_splitter.split_text(p_text)
            if len(child_texts) > 1:
                for c_idx, c_text in enumerate(child_texts):
                    child_chunk = DocumentChunk(
                        document_id=doc.id,
                        parent_id=parent_chunk.id,
                        content=c_text,
                        chunk_type="image_description",
                        page_number=1,
                        chunk_metadata={
                            "parent_index": p_idx,
                            "child_index": c_idx,
                            "level": "child",
                        },
                    )
                    db.add(child_chunk)
                    total_chunks += 1

        await db.commit()
        return total_chunks, total_images, {
            "document_type": "receipt" if is_receipt else "image_diagram",
            "pages": 1,
        }


ingestion_service = IngestionService()

