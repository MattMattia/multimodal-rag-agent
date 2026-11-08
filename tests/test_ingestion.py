"""Ingestion pipeline: leaf-only embeddings, vision errors, orphan PNG cleanup (R2-BUG-03/04/05). Real Postgres."""

import uuid
from unittest.mock import AsyncMock

from httpx import ASGITransport, AsyncClient
import pytest
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.document import Document, DocumentChunk, DocumentImage
from app.services import ingestion as ingestion_module
from app.services.embedding import embedding_service
from app.services.ingestion import ingestion_service
from app.services.vision import vision_service

VISION_ERROR = "[Error al procesar imagen con Gemini: 503 UNAVAILABLE. Archivo: x.png]"


@pytest.fixture
def images_dir(tmp_path, monkeypatch):
    path = tmp_path / "images"
    path.mkdir()
    monkeypatch.setattr(ingestion_module, "UPLOAD_IMAGES_DIR", path)
    return path


@pytest.fixture
def embedded_texts(monkeypatch):
    """Record every text sent to the embedding service and return fixed vectors."""
    texts = []

    async def fake_batch(batch, batch_size=50):
        texts.extend(batch)
        return [[0.1] * 768 for _ in batch]

    monkeypatch.setattr(embedding_service, "get_embeddings_batch", fake_batch)
    return texts


@pytest.fixture
async def doc_ids():
    ids = []
    yield ids
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Document).where(Document.id.in_(ids)))
        await db.commit()


async def _register(ids, path, file_type):
    doc_id = uuid.uuid4()
    ids.append(doc_id)
    async with AsyncSessionLocal() as db:
        db.add(Document(id=doc_id, filename=path.name, file_type=file_type, file_path=str(path),
                        status="pending", doc_metadata={}))
        await db.commit()
    return doc_id


async def _load(doc_id):
    async with AsyncSessionLocal() as db:
        doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one()
        chunks = (await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))).scalars().all()
        images = (await db.execute(select(DocumentImage).where(DocumentImage.document_id == doc_id))).scalars().all()
    return doc, list(chunks), list(images)


def _long_text_pdf(path):
    pdf = canvas.Canvas(str(path))
    y = 800
    for i in range(60):
        pdf.drawString(40, y, f"Linea {i}: el sistema RAG multimodal fusiona recuperacion densa y lexica con RRF.")
        y -= 12
    pdf.showPage()
    pdf.save()


def _image_pdf(path, tmp_path):
    png = tmp_path / "embedded.png"
    Image.new("RGB", (200, 200), (200, 30, 30)).save(png)
    pdf = canvas.Canvas(str(path))
    pdf.drawImage(ImageReader(str(png)), 100, 500, width=200, height=200)
    pdf.drawString(40, 400, "Texto corto de la pagina.")
    pdf.showPage()
    pdf.save()


# ---------------------------------------------------------------------------
# R2-BUG-04: only leaf chunks are embedded
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_only_leaf_chunks_get_embeddings(tmp_path, images_dir, embedded_texts, doc_ids):
    pdf_path = tmp_path / "long.pdf"
    _long_text_pdf(pdf_path)
    doc_id = await _register(doc_ids, pdf_path, "pdf")

    await ingestion_service.process_document_pipeline(doc_id)

    doc, chunks, _ = await _load(doc_id)
    assert doc.status == "completed"
    parent_ids_with_children = {c.parent_id for c in chunks if c.parent_id is not None}
    assert parent_ids_with_children, "fixture must produce parents with children"
    for chunk in chunks:
        if chunk.id in parent_ids_with_children:
            assert chunk.embedding is None
        else:
            assert chunk.embedding is not None
    leaves = [c for c in chunks if c.id not in parent_ids_with_children]
    assert sorted(embedded_texts) == sorted(c.content for c in leaves)
    assert doc.doc_metadata["total_chunks"] == len(chunks)


# ---------------------------------------------------------------------------
# R2-BUG-03: vision errors never become indexable chunks
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pdf_image_with_vision_error_keeps_note_but_no_chunk(tmp_path, images_dir, embedded_texts, doc_ids, monkeypatch):
    monkeypatch.setattr(vision_service, "describe_image", AsyncMock(return_value=VISION_ERROR))
    pdf_path = tmp_path / "img.pdf"
    _image_pdf(pdf_path, tmp_path)
    doc_id = await _register(doc_ids, pdf_path, "pdf")

    await ingestion_service.process_document_pipeline(doc_id)

    doc, chunks, images = await _load(doc_id)
    assert doc.status == "completed"
    assert len(images) == 1
    assert images[0].description == VISION_ERROR
    assert not [c for c in chunks if c.chunk_type == "image_description"]
    assert not any("Error al procesar imagen" in t for t in embedded_texts)
    assert any("Texto corto" in c.content for c in chunks)  # page text still indexed


@pytest.mark.asyncio
async def test_pdf_image_with_description_still_creates_embedded_chunk(tmp_path, images_dir, embedded_texts, doc_ids, monkeypatch):
    monkeypatch.setattr(vision_service, "describe_image", AsyncMock(return_value="Grafico de barras de ingresos"))
    pdf_path = tmp_path / "img.pdf"
    _image_pdf(pdf_path, tmp_path)
    doc_id = await _register(doc_ids, pdf_path, "pdf")

    await ingestion_service.process_document_pipeline(doc_id)

    _, chunks, images = await _load(doc_id)
    image_chunks = [c for c in chunks if c.chunk_type == "image_description"]
    assert len(images) == 1
    assert len(image_chunks) == 1
    assert "Grafico de barras de ingresos" in image_chunks[0].content
    assert image_chunks[0].embedding is not None


@pytest.mark.asyncio
async def test_standalone_image_with_vision_error_creates_no_chunk(tmp_path, images_dir, embedded_texts, doc_ids, monkeypatch):
    monkeypatch.setattr(vision_service, "describe_image", AsyncMock(return_value=VISION_ERROR))
    png = tmp_path / "factura.png"
    Image.new("RGB", (80, 80), (10, 10, 10)).save(png)
    doc_id = await _register(doc_ids, png, "png")

    await ingestion_service.process_document_pipeline(doc_id)

    doc, chunks, images = await _load(doc_id)
    assert doc.status == "completed"
    assert [i.description for i in images] == [VISION_ERROR]
    assert chunks == []
    assert embedded_texts == []


@pytest.mark.asyncio
async def test_standalone_image_description_embeds_leaf_chunks(tmp_path, images_dir, embedded_texts, doc_ids, monkeypatch):
    monkeypatch.setattr(vision_service, "describe_image", AsyncMock(return_value="Factura por 1200 USD"))
    png = tmp_path / "factura.png"
    Image.new("RGB", (80, 80), (10, 10, 10)).save(png)
    doc_id = await _register(doc_ids, png, "png")

    await ingestion_service.process_document_pipeline(doc_id)

    _, chunks, _ = await _load(doc_id)
    assert len(chunks) == 1
    assert chunks[0].parent_id is None
    assert chunks[0].embedding is not None  # standalone text without children is a leaf


# ---------------------------------------------------------------------------
# R2-BUG-05: orphan PNG cleanup on rollback and on delete
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rollback_removes_orphan_images_of_that_document_only(tmp_path, images_dir, doc_ids, monkeypatch):
    pdf_path = tmp_path / "boom.pdf"
    _long_text_pdf(pdf_path)
    doc_id = await _register(doc_ids, pdf_path, "pdf")
    orphan = images_dir / f"{doc_id}_p1_img1.png"
    other_doc_file = images_dir / f"{uuid.uuid4()}_p1_img1.png"
    other_doc_file.write_bytes(b"other")

    async def exploding_pdf(self, db, doc, file_path):
        orphan.write_bytes(b"png")
        raise RuntimeError("boom")

    monkeypatch.setattr(type(ingestion_service), "_process_pdf", exploding_pdf)

    await ingestion_service.process_document_pipeline(doc_id)

    doc, chunks, _ = await _load(doc_id)
    assert doc.status == "failed"
    assert "boom" in doc.error_message
    assert not orphan.exists()
    assert other_doc_file.exists()


@pytest.mark.asyncio
async def test_failed_embedding_fails_document_and_cleans_images(tmp_path, images_dir, doc_ids, monkeypatch):
    monkeypatch.setattr(vision_service, "describe_image", AsyncMock(return_value="desc"))
    monkeypatch.setattr(embedding_service, "get_embeddings_batch", AsyncMock(side_effect=RuntimeError("503 after retries")))
    pdf_path = tmp_path / "img.pdf"
    _image_pdf(pdf_path, tmp_path)
    doc_id = await _register(doc_ids, pdf_path, "pdf")

    await ingestion_service.process_document_pipeline(doc_id)

    doc, chunks, images = await _load(doc_id)
    assert doc.status == "failed"
    assert chunks == [] and images == []
    assert list(images_dir.glob(f"{doc_id}_*")) == []


@pytest.mark.asyncio
async def test_delete_document_removes_orphan_images_by_glob(tmp_path, images_dir, doc_ids, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "")
    doc_file = tmp_path / "doc.pdf"
    doc_file.write_bytes(b"%PDF-")
    doc_id = await _register(doc_ids, doc_file, "pdf")
    orphan = images_dir / f"{doc_id}_p2_img3.png"
    orphan.write_bytes(b"png")
    other = images_dir / f"{uuid.uuid4()}_p1_img1.png"
    other.write_bytes(b"keep")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(f"/api/v1/documents/{doc_id}")

    assert resp.status_code == 204
    assert not doc_file.exists()
    assert not orphan.exists()
    assert other.exists()
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none() is None
