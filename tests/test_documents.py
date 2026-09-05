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

