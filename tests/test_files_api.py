"""Authenticated file endpoints under /api/v1 (R2-BUG-01): reports, original documents and extracted images."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.document import Document, DocumentImage

API_KEY = "s3cret"
HEADERS = {"X-API-Key": API_KEY}
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-png-body"


class _Dirs:
    def __init__(self, reports, documents, images, root):
        self.reports, self.documents, self.images, self.root = reports, documents, images, root


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    """Point every served directory to an isolated tmp_path and require the API key."""
    reports, documents, images = tmp_path / "reports", tmp_path / "documents", tmp_path / "images"
    for d in (reports, documents, images):
        d.mkdir()
    monkeypatch.setattr(settings, "API_KEY", API_KEY)
    monkeypatch.setattr("app.api.v1.endpoints.files.REPORTS_DIR", reports)
    monkeypatch.setattr("app.api.v1.endpoints.files.DOCUMENTS_DIR", documents)
    monkeypatch.setattr("app.api.v1.endpoints.files.IMAGES_DIR", images)
    return _Dirs(reports, documents, images, tmp_path)


@pytest.fixture
def http():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def doc_ids():
    """Collects created document ids and removes them (cascade) after the test."""
    ids = []
    yield ids
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Document).where(Document.id.in_(ids)))
        await db.commit()


async def _create_document(ids, file_path, images=()):
    doc_id = uuid.uuid4()
    ids.append(doc_id)
    image_ids = []
    async with AsyncSessionLocal() as db:
        db.add(Document(id=doc_id, filename="doc.pdf", file_type="pdf", file_path=str(file_path),
                        status="completed", doc_metadata={}))
        await db.flush()
        for path in images:
            image_id = uuid.uuid4()
            image_ids.append(image_id)
            db.add(DocumentImage(id=image_id, document_id=doc_id, image_path=str(path),
                                 description="d", page_number=1, image_metadata={}))
        await db.commit()
    return doc_id, image_ids


# ---------------------------------------------------------------------------
# /api/v1/reports/{filename}
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_report_endpoint_serves_inline_pdf_with_auth(dirs, http):
    (dirs.reports / "r.pdf").write_bytes(b"%PDF-1.4 data")
    async with http as client:
        no_key = await client.get("/api/v1/reports/r.pdf")
        ok = await client.get("/api/v1/reports/r.pdf", headers=HEADERS)
    assert no_key.status_code == 401
    assert ok.status_code == 200
    assert ok.content == b"%PDF-1.4 data"
    assert ok.headers["content-type"] == "application/pdf"
    assert ok.headers["content-disposition"] == 'inline; filename="r.pdf"'


@pytest.mark.asyncio
async def test_report_endpoint_rejects_traversal_missing_and_non_pdf(dirs, http):
    (dirs.root / "outside.pdf").write_bytes(b"%PDF-secret")
    (dirs.reports / "notes.txt").write_text("x")
    async with http as client:
        traversal = await client.get("/api/v1/reports/..%2Foutside.pdf", headers=HEADERS)
        missing = await client.get("/api/v1/reports/none.pdf", headers=HEADERS)
        non_pdf = await client.get("/api/v1/reports/notes.txt", headers=HEADERS)
    assert traversal.status_code == 404
    assert b"secret" not in traversal.content
    assert missing.status_code == 404
    assert non_pdf.status_code == 404


@pytest.mark.asyncio
async def test_legacy_reports_route_still_serves_pdf(dirs, http, monkeypatch):
    monkeypatch.setattr("app.main.REPORTS_DIR", dirs.reports)
    (dirs.reports / "legacy.pdf").write_bytes(b"%PDF-1.4 legacy")
    async with http as client:
        no_key = await client.get("/uploads/reports/legacy.pdf")
        ok = await client.get("/uploads/reports/legacy.pdf", headers=HEADERS)
    assert no_key.status_code == 401
    assert ok.status_code == 200
    assert ok.content == b"%PDF-1.4 legacy"


# ---------------------------------------------------------------------------
# /api/v1/documents/{id}/file
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_document_file_serves_original_upload(dirs, http, doc_ids):
    path = dirs.documents / "orig.pdf"
    path.write_bytes(b"%PDF-1.4 original")
    doc_id, _ = await _create_document(doc_ids, path)
    async with http as client:
        no_key = await client.get(f"/api/v1/documents/{doc_id}/file")
        ok = await client.get(f"/api/v1/documents/{doc_id}/file", headers=HEADERS)
        unknown = await client.get(f"/api/v1/documents/{uuid.uuid4()}/file", headers=HEADERS)
    assert no_key.status_code == 401
    assert ok.status_code == 200
    assert ok.content == b"%PDF-1.4 original"
    assert ok.headers["content-type"] == "application/pdf"
    assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_document_file_outside_uploads_dir_is_404(dirs, http, doc_ids):
    outside = dirs.root / "secret.pdf"
    outside.write_bytes(b"%PDF-secret")
    doc_id, _ = await _create_document(doc_ids, outside)
    async with http as client:
        resp = await client.get(f"/api/v1/documents/{doc_id}/file", headers=HEADERS)
    assert resp.status_code == 404
    assert b"secret" not in resp.content


# ---------------------------------------------------------------------------
# /api/v1/documents/{id}/images/{image_id}/file
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name, mime",
    [("a.png", "image/png"), ("a.jpg", "image/jpeg"), ("a.jpeg", "image/jpeg"), ("a.webp", "image/webp")],
)
async def test_image_file_served_with_mime_type(dirs, http, doc_ids, name, mime):
    path = dirs.images / name
    path.write_bytes(PNG_BYTES)
    doc_id, (image_id,) = await _create_document(doc_ids, dirs.documents / "x.pdf", images=[path])
    async with http as client:
        no_key = await client.get(f"/api/v1/documents/{doc_id}/images/{image_id}/file")
        ok = await client.get(f"/api/v1/documents/{doc_id}/images/{image_id}/file", headers=HEADERS)
    assert no_key.status_code == 401
    assert ok.status_code == 200
    assert ok.content == PNG_BYTES
    assert ok.headers["content-type"] == mime


@pytest.mark.asyncio
async def test_image_must_belong_to_document(dirs, http, doc_ids):
    path = dirs.images / "a.png"
    path.write_bytes(PNG_BYTES)
    _, (image_id,) = await _create_document(doc_ids, dirs.documents / "x.pdf", images=[path])
    other_doc, _ = await _create_document(doc_ids, dirs.documents / "y.pdf")
    async with http as client:
        wrong_doc = await client.get(f"/api/v1/documents/{other_doc}/images/{image_id}/file", headers=HEADERS)
        unknown_image = await client.get(
            f"/api/v1/documents/{other_doc}/images/{uuid.uuid4()}/file", headers=HEADERS
        )
    assert wrong_doc.status_code == 404
    assert unknown_image.status_code == 404


@pytest.mark.asyncio
async def test_image_outside_images_dir_is_404(dirs, http, doc_ids):
    outside = dirs.root / "secret.png"
    outside.write_bytes(PNG_BYTES)
    doc_id, (image_id,) = await _create_document(doc_ids, dirs.documents / "x.pdf", images=[outside])
    async with http as client:
        resp = await client.get(f"/api/v1/documents/{doc_id}/images/{image_id}/file", headers=HEADERS)
    assert resp.status_code == 404
    assert PNG_BYTES not in resp.content
