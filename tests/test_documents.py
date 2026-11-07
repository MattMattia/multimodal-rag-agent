import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.ingestion import IngestionService, table_to_markdown
from app.services.vision import VisionService


def test_table_to_markdown():
    """Valida la conversión de celdas de pdfplumber a formato Markdown estándar."""
    raw_table = [
        ["Producto", "Cantidad", "Precio"],
        ["Servidor GPU", "2", "$5000"],
        ["Licencia Software", "1", "$1200"],
    ]
    md = table_to_markdown(raw_table)
    assert "| Producto | Cantidad | Precio |" in md
    assert "| --- | --- | --- |" in md
    assert "| Servidor GPU | 2 | $5000 |" in md


def test_table_to_markdown_empty():
    """Valida que tablas vacías retornen cadena vacía sin fallar."""
    assert table_to_markdown([]) == ""
    assert table_to_markdown([[]]) == ""


def test_hierarchical_chunker():
    """Valida que los splitters dividan adecuadamente textos largos en bloques padre e hijos."""
    ingestion = IngestionService(
        parent_chunk_size=100,
        parent_chunk_overlap=10,
        child_chunk_size=40,
        child_chunk_overlap=5,
    )
    long_text = (
        "El procesamiento del lenguaje natural y la visión computacional permiten crear agentes "
        "inteligentes capaces de razonar sobre tablas, textos e imágenes de documentos complejos "
        "sin perder contexto semántico ni jerárquico."
    )
    parents = ingestion.parent_splitter.split_text(long_text)
    assert len(parents) >= 1

    children = ingestion.child_splitter.split_text(parents[0])
    assert len(children) >= 1


@pytest.mark.asyncio
async def test_upload_unsupported_format():
    """Valida que el endpoint /upload rechace formatos no soportados como .exe o .txt."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        files = {"file": ("script.sh", b"#!/bin/bash\necho hello", "text/x-sh")}
        response = await client.post("/api/v1/documents/upload", files=files)
        assert response.status_code == 400
        data = response.json()
        assert "Formato no soportado" in data["detail"]


@pytest.mark.asyncio
async def test_vision_placeholder_without_key():
    """Valida que el servicio de visión maneje de forma segura imágenes cuando no hay API key."""
    service = VisionService()
    # Forzar modo no inicializado
    service._initialized = False
    result = await service.describe_image("non_existent_file.png")
    assert "no encontrado" in result.lower()



# ---------------------------------------------------------------------------
# SEC-02: upload hardening (no DB, no Gemini, files confined to tmp_path)
# ---------------------------------------------------------------------------
@pytest.fixture
def upload_env(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from app.api.v1.endpoints import documents as documents_module
    from app.core.config import settings
    from app.core.database import get_db

    monkeypatch.setattr(settings, "API_KEY", "")
    monkeypatch.setattr(documents_module, "UPLOAD_DOCS_DIR", tmp_path)
    pipeline = AsyncMock()
    monkeypatch.setattr(documents_module.ingestion_service, "process_document_pipeline", pipeline)

    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    yield tmp_path, session
    app.dependency_overrides.pop(get_db, None)


async def _upload(name, body, content_type):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/api/v1/documents/upload", files={"file": (name, body, content_type)})


@pytest.mark.asyncio
async def test_upload_sanitizes_traversal_filename(upload_env):
    tmp_path, session = upload_env
    resp = await _upload("../../evil.pdf", b"%PDF-1.4 hello", "application/pdf")
    assert resp.status_code == 202
    body = resp.json()
    assert body["filename"] == "evil.pdf"
    assert body["file_type"] == "pdf"
    assert body["status"] == "pending"
    saved = list(tmp_path.iterdir())
    assert len(saved) == 1
    assert saved[0].name.endswith("_evil.pdf")
    assert saved[0].resolve().is_relative_to(tmp_path.resolve())
    assert not (tmp_path.parent / "evil.pdf").exists()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_rejects_html_with_pdf_content_type(upload_env):
    tmp_path, session = upload_env
    resp = await _upload("page.html", b"<html></html>", "application/pdf")
    assert resp.status_code == 400
    assert "Formato no soportado" in resp.json()["detail"]
    assert list(tmp_path.iterdir()) == []
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_rejects_pdf_without_pdf_magic_bytes(upload_env):
    tmp_path, session = upload_env
    resp = await _upload("fake.pdf", b"<html>not a pdf</html>", "application/pdf")
    assert resp.status_code == 400
    assert list(tmp_path.iterdir()) == []
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_accepts_png_with_magic_bytes(upload_env):
    tmp_path, _ = upload_env
    resp = await _upload("pic.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, "image/png")
    assert resp.status_code == 202
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.asyncio
async def test_upload_over_limit_returns_413_and_removes_file(upload_env, monkeypatch):
    from app.core.config import settings

    tmp_path, session = upload_env
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 0.0001)  # ~104 bytes
    resp = await _upload("big.pdf", b"%PDF-" + b"A" * 70000, "application/pdf")
    assert resp.status_code == 413
    assert list(tmp_path.iterdir()) == []
    session.commit.assert_not_awaited()
