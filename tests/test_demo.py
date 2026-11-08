"""S9: Golden Corpus seeder, /demo/seed and /demo/status."""

import time
from unittest.mock import AsyncMock, patch

import pdfplumber
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.core import database
from app.core.config import settings
from app.main import app
from app.models.document import Document, DocumentChunk, DocumentImage
from app.schemas.search import SearchRequest
from app.services import demo_seeder
from app.services.rag_search import hybrid_search_service

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
STATUS_FIELDS = {
    "db_dialect", "demo_seeded", "total_documents", "total_chunks", "total_images",
    "gemini_configured", "langfuse_enabled", "active_models", "embedding_mode",
}


@pytest.fixture
def http():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _count(model):
    async with database.AsyncSessionLocal() as db:
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def test_seed_endpoint_creates_documents_files_and_is_fast_offline(http, sqlite_db, demo_dirs):
    documents_dir, images_dir = demo_dirs
    started = time.perf_counter()
    async with http as client:
        resp = await client.post("/api/v1/demo/seed")
    elapsed = time.perf_counter() - started
    print(f"\n[demo/seed offline] {elapsed * 1000:.0f} ms")
    assert resp.status_code == 200
    body = resp.json()
    assert body["documents_created"] == 3 and body["documents_skipped"] == 0
    assert elapsed < 3.0  # the spec target is < 1 s; generous bound against CI flakiness

    pdfs = sorted(documents_dir.glob("*.pdf"))
    assert {p.name for p in pdfs} == {
        "Arquitectura_Cloud_IA_2026.pdf",
        "Reporte_Financiero_Q3_GlobalTech.pdf",
        "Manual_Seguridad_ZeroTrust_OWASP.pdf",
    }
    for pdf in pdfs:
        assert pdf.read_bytes().startswith(b"%PDF-")
    pngs = sorted(images_dir.glob("*.png"))
    assert len(pngs) == 3
    for png in pngs:
        assert png.read_bytes().startswith(PNG_SIGNATURE)
    with pdfplumber.open(documents_dir / "Reporte_Financiero_Q3_GlobalTech.pdf") as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "45M" in text and "EBITDA" in text


async def test_seed_is_idempotent_and_regenerates_missing_files(http, sqlite_db, demo_dirs):
    documents_dir, images_dir = demo_dirs
    async with http as client:
        await client.post("/api/v1/demo/seed")
        before = (await _count(Document), await _count(DocumentChunk), await _count(DocumentImage))
        (documents_dir / "Arquitectura_Cloud_IA_2026.pdf").unlink()
        second = (await client.post("/api/v1/demo/seed")).json()
    after = (await _count(Document), await _count(DocumentChunk), await _count(DocumentImage))
    assert before == after and before[0] == 3 and before[2] == 3
    assert second["documents_created"] == 0 and second["documents_skipped"] == 3
    assert second["files_created"] == 1
    assert (documents_dir / "Arquitectura_Cloud_IA_2026.pdf").read_bytes().startswith(b"%PDF-")


async def test_status_before_and_after_seeding(http, sqlite_db, demo_dirs):
    async with http as client:
        empty = (await client.get("/api/v1/demo/status")).json()
        await client.post("/api/v1/demo/seed")
        seeded = (await client.get("/api/v1/demo/status")).json()
    assert set(empty) == STATUS_FIELDS and set(seeded) == STATUS_FIELDS
    assert empty["demo_seeded"] is False and empty["total_documents"] == 0
    assert seeded["demo_seeded"] is True
    assert seeded["total_documents"] == 3 and seeded["total_images"] == 3 and seeded["total_chunks"] > 10
    assert seeded["db_dialect"] == "sqlite"
    assert seeded["gemini_configured"] is False and seeded["langfuse_enabled"] is False
    assert seeded["embedding_mode"] == "mock"
    assert isinstance(seeded["active_models"], dict) and seeded["active_models"]["agent"] == settings.GEMINI_AGENT_MODEL


async def test_seeded_content_has_the_golden_figures_hierarchy_and_leaf_only_embeddings(sqlite_db, demo_dirs):
    vision = AsyncMock(side_effect=AssertionError("Gemini Vision must not be called while seeding"))
    with patch("app.services.vision.vision_service.describe_image", vision):
        await demo_seeder.seed_demo_corpus()
    async with database.AsyncSessionLocal() as db:
        chunks = (await db.execute(select(DocumentChunk))).scalars().all()
    corpus = "\n".join(c.content for c in chunks)
    for figure in ("$45M", "$28M", "$19M", "34%", "m=16", "ef_construction=64", "k=60", "X-API-Key", "SSRF", "P95"):
        assert figure in corpus, figure
    assert {"text", "table", "image_description"} <= {c.chunk_type for c in chunks}
    assert any(c.content.lstrip().startswith("###") and "|" in c.content for c in chunks if c.chunk_type == "table")
    parent_ids = {c.parent_id for c in chunks if c.parent_id}
    children = [c for c in chunks if c.parent_id]
    assert children and all(c.embedding is not None and len(c.embedding) == settings.EMBEDDING_DIMENSION for c in children)
    assert all(c.embedding is None for c in chunks if c.id in parent_ids)  # parents are context only
    assert all(c.embedding is not None for c in chunks if c.id not in parent_ids)  # every leaf is searchable
    vision.assert_not_awaited()
    # each table is indexed once (standalone table chunk), not again inside the page text chunks
    assert sum(1 for c in chunks if "Norteamérica | $45M" in c.content) == 1


async def test_auto_seed_after_init_db_only_when_documents_is_empty(sqlite_db, demo_dirs, monkeypatch):
    monkeypatch.setattr(settings, "AUTO_SEED_DEMO_CORPUS", True)
    await database.init_db()
    assert await _count(Document) == 3

    # a non-empty database is never touched
    async with database.AsyncSessionLocal() as db:
        await db.execute(Document.__table__.delete().where(Document.filename != "Reporte_Financiero_Q3_GlobalTech.pdf"))
        await db.commit()
    await database.init_db()
    assert await _count(Document) == 1


async def test_auto_seed_disabled_leaves_database_empty(sqlite_db, demo_dirs, monkeypatch):
    monkeypatch.setattr(settings, "AUTO_SEED_DEMO_CORPUS", False)
    await database.init_db()
    assert await _count(Document) == 0


async def test_seeded_files_are_served_by_the_authenticated_file_endpoints(http, sqlite_db, demo_dirs, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "k")
    headers = {"X-API-Key": "k"}
    async with http as client:
        assert (await client.post("/api/v1/demo/seed", headers=headers)).status_code == 200
        async with database.AsyncSessionLocal() as db:
            doc = (await db.execute(select(Document).where(Document.filename.like("Reporte%")))).scalar_one()
            image = (await db.execute(select(DocumentImage).where(DocumentImage.document_id == doc.id))).scalar_one()
        pdf = await client.get(f"/api/v1/documents/{doc.id}/file", headers=headers)
        png = await client.get(f"/api/v1/documents/{doc.id}/images/{image.id}/file", headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert png.status_code == 200 and png.content.startswith(PNG_SIGNATURE)


async def test_demo_endpoints_require_the_api_key(http, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "k")
    async with http as client:
        assert (await client.get("/api/v1/demo/status")).status_code == 401
        assert (await client.post("/api/v1/demo/seed")).status_code == 401
        assert (await client.post("/api/v1/demo/evaluate")).status_code == 401


async def test_seeded_corpus_is_searchable_on_the_main_database(demo_dirs):
    """Runs on whichever database the suite uses (PostgreSQL or SQLite); everything is rolled back."""
    async with database.AsyncSessionLocal() as db:
        try:
            await demo_seeder.seed_golden_corpus(db)  # flush only, the caller owns the transaction
            request = SearchRequest(query="EBITDA margen", top_k=3, mode="sparse", rerank=False)
            response = await hybrid_search_service.search(db=db, request=request)
            assert response.results
            assert any(r.document_name == "Reporte_Financiero_Q3_GlobalTech.pdf" for r in response.results)
            assert response.diagnostics.db_dialect == database.get_active_db_dialect()
        finally:
            await db.rollback()
