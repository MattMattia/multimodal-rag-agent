"""Siembra idempotente del Golden Demo Corpus (3 PDFs + 3 PNGs físicos) sin llamar a Gemini Vision.

Los archivos se generan en disco (ReportLab y Pillow) solo si faltan, de modo que los endpoints de archivos
sirven binarios reales y válidos. Las filas de BD (documentos, chunks padre/hijo, tablas, descripciones de imagen y
embeddings vía `EmbeddingService`, que devuelve vectores determinísticos sin API key) se insertan en una sola
transacción y se omiten si el documento ya existe (id determinístico por nombre de archivo).
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database
from app.core.config import settings
from app.core.telemetry import telemetry_service
from app.models.document import Document, DocumentChunk, DocumentImage
from app.services.demo_corpus import GOLDEN_DOCUMENTS, GOLDEN_FILENAMES, GoldenDocument, GoldenPage  # noqa: F401
from app.services.embedding import embedding_service
from app.services.ingestion import IngestionService

logger = logging.getLogger(__name__)

# Directorios de salida (los tests y los endpoints de archivos los sustituyen por directorios temporales)
DOCUMENTS_DIR = Path("uploads/documents")
IMAGES_DIR = Path("uploads/images")

DEMO_NAMESPACE = uuid.UUID("6f1f0c58-5e0e-4b8e-9d0c-6d1d0e6a7c11")
IMAGE_SIZE = (900, 520)


def golden_document_id(filename: str) -> uuid.UUID:
    """Id determinístico del documento demo: el re-sembrado nunca duplica filas."""
    return uuid.uuid5(DEMO_NAMESPACE, filename)


@dataclass
class SeedResult:
    documents_created: int = 0
    documents_skipped: int = 0
    files_created: int = 0
    chunks_created: int = 0
    images_created: int = 0


# --------------------------------------------------------------------------------------------------
# Imágenes (Pillow ImageDraw)
# --------------------------------------------------------------------------------------------------
def _font(size: int) -> Any:
    for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _box(draw: ImageDraw.ImageDraw, xy, label: str, fill: str, font: Any) -> None:
    draw.rounded_rectangle(xy, radius=10, fill=fill, outline="#1f2937", width=2)
    x0, y0, x1, y1 = xy
    draw.text(((x0 + x1) / 2, (y0 + y1) / 2), label, fill="white", font=font, anchor="mm")


def _arrow(draw: ImageDraw.ImageDraw, start, end) -> None:
    draw.line([start, end], fill="#374151", width=3)
    ex, ey = end
    draw.ellipse((ex - 5, ey - 5, ex + 5, ey + 5), fill="#374151")


def _draw_architecture(draw: ImageDraw.ImageDraw, title_font: Any, font: Any) -> None:
    draw.text((450, 30), "Arquitectura de microservicios", fill="#111827", font=title_font, anchor="mm")
    _box(draw, (40, 220, 190, 300), "Cliente", "#2563eb", font)
    _box(draw, (250, 220, 420, 300), "API Gateway", "#7c3aed", font)
    for i, label in enumerate(("Ingesta", "Busqueda hibrida", "Agente IA")):
        top = 90 + i * 130
        _box(draw, (500, top, 690, top + 70), label, "#059669", font)
        _arrow(draw, (420, 260), (500, top + 35))
    _box(draw, (760, 190, 880, 330), "PostgreSQL\npgvector\nHNSW", "#b45309", font)
    for i in range(3):
        _arrow(draw, (690, 125 + i * 130), (760, 260))
    _box(draw, (500, 450, 690, 505), "Langfuse", "#be123c", font)
    _arrow(draw, (190, 260), (250, 260))


def _draw_bars(draw: ImageDraw.ImageDraw, title_font: Any, font: Any) -> None:
    draw.text((450, 30), "Ingresos Q3 por region (USD M)", fill="#111827", font=title_font, anchor="mm")
    base_y, scale = 450, 7.0
    draw.line([(80, base_y), (850, base_y)], fill="#111827", width=3)
    draw.line([(80, 70), (80, base_y)], fill="#111827", width=3)
    for i, (label, value, color) in enumerate((("Norteamerica", 45, "#2563eb"), ("EMEA", 28, "#059669"), ("LATAM", 19, "#d97706"))):
        x0 = 150 + i * 240
        top = base_y - value * scale
        draw.rectangle((x0, top, x0 + 150, base_y), fill=color, outline="#111827", width=2)
        draw.text((x0 + 75, top - 18), f"${value}M", fill="#111827", font=title_font, anchor="mm")
        draw.text((x0 + 75, base_y + 24), label, fill="#111827", font=font, anchor="mm")


def _draw_matrix(draw: ImageDraw.ImageDraw, title_font: Any, font: Any) -> None:
    draw.text((450, 30), "Matriz de riesgo OWASP", fill="#111827", font=title_font, anchor="mm")
    palette = [["#fde68a", "#fdba74", "#fca5a5"], ["#bbf7d0", "#fde68a", "#fdba74"], ["#bbf7d0", "#bbf7d0", "#fde68a"]]
    cell_w, cell_h, x_origin, y_origin = 230, 120, 120, 80
    for row in range(3):
        for col in range(3):
            x0, y0 = x_origin + col * cell_w, y_origin + row * cell_h
            draw.rectangle((x0, y0, x0 + cell_w, y0 + cell_h), fill=palette[row][col], outline="#111827", width=2)
    draw.text((x_origin + 2.5 * cell_w, y_origin + 0.5 * cell_h), "A01  A03  A10", fill="#7f1d1d", font=font, anchor="mm")
    draw.text((x_origin + 1.5 * cell_w, y_origin + 1.5 * cell_h), "A04  A09", fill="#78350f", font=font, anchor="mm")
    draw.text((450, 475), "Probabilidad (->)  /  Impacto (^)", fill="#111827", font=font, anchor="mm")


_IMAGE_DRAWERS = {"architecture": _draw_architecture, "bars": _draw_bars, "matrix": _draw_matrix}


def _generate_png(doc: GoldenDocument, path: Path) -> None:
    image = Image.new("RGB", IMAGE_SIZE, "white")
    draw = ImageDraw.Draw(image)
    _IMAGE_DRAWERS[doc.image_kind](draw, _font(26), _font(18))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


# --------------------------------------------------------------------------------------------------
# PDFs (ReportLab)
# --------------------------------------------------------------------------------------------------
def _generate_pdf(doc: GoldenDocument, pdf_path: Path, image_path: Path) -> None:
    styles = getSampleStyleSheet()
    story: List[Any] = [Paragraph(escape(doc.title), styles["Title"]), Spacer(1, 0.3 * cm)]
    for page_index, page in enumerate(doc.pages):
        if page_index:
            story.append(PageBreak())
        for heading, text in page.sections:
            story.append(Paragraph(escape(heading), styles["Heading2"]))
            story.append(Paragraph(escape(text), styles["BodyText"]))
            story.append(Spacer(1, 0.2 * cm))
        if page.table:
            story.append(Paragraph(escape(page.table_title), styles["Heading3"]))
            data = [list(page.table.header)] + [list(row) for row in page.table.rows]
            table = Table(data, hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ]
                )
            )
            story.extend([table, Spacer(1, 0.4 * cm)])
        if page.show_image:
            width = 14 * cm
            story.append(RLImage(str(image_path), width=width, height=width * IMAGE_SIZE[1] / IMAGE_SIZE[0]))
            story.append(Paragraph(escape(doc.image_caption), styles["Italic"]))
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(pdf_path), pagesize=A4, title=doc.title, author="Sistema RAG Multimodal").build(story)


def ensure_demo_files() -> int:
    """Genera en disco los PDFs y PNGs del corpus que falten. Devuelve cuántos archivos creó."""
    created = 0
    for doc in GOLDEN_DOCUMENTS:
        image_path = IMAGES_DIR / doc.image_filename
        pdf_path = DOCUMENTS_DIR / doc.filename
        if not image_path.is_file():
            _generate_png(doc, image_path)
            created += 1
        if not pdf_path.is_file():
            _generate_pdf(doc, pdf_path, image_path)
            created += 1
    return created


# --------------------------------------------------------------------------------------------------
# Base de datos
# --------------------------------------------------------------------------------------------------
def _add_document_rows(db: AsyncSession, golden: GoldenDocument, ingestion: IngestionService) -> Dict[str, int]:
    """Añade a la sesión el documento, la imagen y todos los chunks (mismo formato que la ingesta real)."""
    doc_id = golden_document_id(golden.filename)
    doc = Document(
        id=doc_id,
        filename=golden.filename,
        file_type="application/pdf",
        file_path=str(DOCUMENTS_DIR / golden.filename),
        status="completed",
        doc_metadata={"demo_corpus": True},
    )
    db.add(doc)

    chunks = 0
    tables = 0
    for page_number, page in enumerate(golden.pages, start=1):
        if page.table:
            tables += 1
            table_md = f"### [Tabla Página {page_number} - Ítem 1]\n{page.table.to_markdown()}"
            db.add(
                DocumentChunk(
                    document_id=doc_id,
                    parent_id=None,
                    content=table_md,
                    chunk_type="table",
                    page_number=page_number,
                    chunk_metadata={"table_index": 1, "level": "parent"},
                )
            )
            chunks += 1
        if page.show_image:
            image_path = IMAGES_DIR / golden.image_filename
            db.add(
                DocumentImage(
                    document_id=doc_id,
                    image_path=str(image_path),
                    description=golden.image_description,
                    page_number=page_number,
                    image_metadata={"image_index": 1, "demo_corpus": True},
                )
            )
            db.add(
                DocumentChunk(
                    document_id=doc_id,
                    parent_id=None,
                    content=(
                        f"### [Imagen/Diagrama Técnico - Página {page_number}]\n"
                        f"Archivo: {golden.image_filename}\n"
                        f"Descripción del gráfico: {golden.image_description}"
                    ),
                    chunk_type="image_description",
                    page_number=page_number,
                    chunk_metadata={"image_path": str(image_path), "level": "parent"},
                )
            )
            chunks += 1
        page_text = "\n\n".join(f"{heading}\n{text}" for heading, text in page.sections)
        if page_text.strip():
            chunks += ingestion._add_hierarchical_chunks(  # reutiliza el chunking padre-hijo de la ingesta real
                db=db,
                doc=doc,
                text=page_text,
                chunk_type="text",
                page_number=page_number,
                prefix_first="",
                extra_parent_metadata={},
            )
    doc.doc_metadata = {
        "demo_corpus": True,
        "total_pages": len(golden.pages),
        "total_tables": tables,
        "total_images": 1,
        "total_chunks": chunks,
    }
    return {"chunks": chunks, "images": 1}


async def _embed_leaf_chunks(db: AsyncSession, document_ids: List[uuid.UUID]) -> None:
    """Vectoriza solo los chunks hoja (los padres con hijos quedan sin embedding, igual que en la ingesta)."""
    await db.flush()
    chunks = (
        (await db.execute(select(DocumentChunk).where(DocumentChunk.document_id.in_(document_ids)))).scalars().all()
    )
    parent_ids = {c.parent_id for c in chunks if c.parent_id is not None}
    leaves = [c for c in chunks if c.id not in parent_ids]
    vectors = await embedding_service.get_embeddings_batch([c.content for c in leaves])
    for chunk, vector in zip(leaves, vectors):
        chunk.embedding = vector


async def seed_golden_corpus(db: AsyncSession) -> SeedResult:
    """Siembra el Golden Corpus en `db` (solo flush: quien llama controla la transacción). Idempotente."""
    result = SeedResult()
    result.files_created = await asyncio.to_thread(ensure_demo_files)

    wanted = {d.filename: golden_document_id(d.filename) for d in GOLDEN_DOCUMENTS}
    existing = set(
        (await db.execute(select(Document.id).where(Document.id.in_(list(wanted.values()))))).scalars().all()
    )

    ingestion = IngestionService()
    new_ids: List[uuid.UUID] = []
    for golden in GOLDEN_DOCUMENTS:
        if wanted[golden.filename] in existing:
            result.documents_skipped += 1
            continue
        counts = _add_document_rows(db, golden, ingestion)
        result.documents_created += 1
        result.chunks_created += counts["chunks"]
        result.images_created += counts["images"]
        new_ids.append(wanted[golden.filename])

    if new_ids:
        await _embed_leaf_chunks(db, new_ids)
    return result


async def seed_demo_corpus() -> Dict[str, Any]:
    """Abre su propia sesión, siembra el corpus y confirma la transacción. Devuelve el resumen con la duración."""
    started = time.perf_counter()
    async with database.AsyncSessionLocal() as db:
        result = await seed_golden_corpus(db)
        await db.commit()
    summary = asdict(result)
    summary["duration_ms"] = round((time.perf_counter() - started) * 1000.0, 1)
    return summary


async def seed_demo_corpus_if_empty() -> bool:
    """Auto-siembra solo si la tabla `documents` no tiene registros. Devuelve True si sembró."""
    async with database.AsyncSessionLocal() as db:
        total = (await db.execute(select(func.count()).select_from(Document))).scalar_one()
    if total:
        return False
    summary = await seed_demo_corpus()
    logger.info("Golden Corpus sembrado automáticamente: %s", summary)
    return True


async def get_demo_status(db: AsyncSession) -> Dict[str, Any]:
    """Estado del demo: dialecto, si el corpus está sembrado, totales y configuración activa."""
    wanted = [golden_document_id(name) for name in GOLDEN_FILENAMES]
    seeded_count = (
        await db.execute(select(func.count()).select_from(Document).where(Document.id.in_(wanted)))
    ).scalar_one()
    total_documents = (await db.execute(select(func.count()).select_from(Document))).scalar_one()
    total_chunks = (await db.execute(select(func.count()).select_from(DocumentChunk))).scalar_one()
    total_images = (await db.execute(select(func.count()).select_from(DocumentImage))).scalar_one()
    return {
        "db_dialect": database.get_active_db_dialect(),
        "demo_seeded": seeded_count == len(wanted),
        "total_documents": total_documents,
        "total_chunks": total_chunks,
        "total_images": total_images,
        "gemini_configured": gemini_configured(),
        "langfuse_enabled": bool(telemetry_service.is_enabled),
        "embedding_mode": "gemini" if gemini_configured() else "mock",
        "active_models": {
            "agent": settings.GEMINI_AGENT_MODEL,
            "vision": settings.GEMINI_VISION_MODEL,
            "embedding": settings.GEMINI_EMBEDDING_MODEL,
        },
    }


def gemini_configured() -> bool:
    """True si hay una GOOGLE_API_KEY real (no vacía ni el placeholder del .env.example)."""
    import os

    key = (os.environ.get("GOOGLE_API_KEY") or settings.GOOGLE_API_KEY or "").strip()
    return bool(key) and not key.startswith("tu_google")
