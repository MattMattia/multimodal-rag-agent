import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.embedding import embedding_service
from app.services.rag_search import hybrid_search_service


@pytest.mark.asyncio
async def test_embedding_dimensions():
    """Verifica que el servicio genere embeddings con exactamente 768 dimensiones."""
    vector = await embedding_service.get_embedding("Inteligencia Artificial y RAG Multimodal")
    assert isinstance(vector, list)
    assert len(vector) == 768
    # Verificar que los elementos sean números de punto flotante
    assert all(isinstance(x, float) for x in vector)


@pytest.mark.asyncio
async def test_embedding_batch_generation():
    """Verifica que la generación de embeddings por lotes mantenga la correlación de tamaño."""
    texts = [
        "Procesamiento de facturas y recibos",
        "Extracción de tablas en formato Markdown",
        "Algoritmo Reciprocal Rank Fusion",
    ]
    vectors = await embedding_service.get_embeddings_batch(texts, batch_size=2)
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == 768


def test_reciprocal_rank_fusion_logic():
    """Verifica que el algoritmo RRF favorezca elementos presentes tanto en la lista densa como en la esparsa."""
    doc_a = uuid.uuid4()
    doc_b = uuid.uuid4()
    doc_c = uuid.uuid4()

    dense_results = [
        {"chunk_id": doc_a, "content": "Doc A", "document_id": uuid.uuid4(), "document_name": "a.pdf", "chunk_type": "text", "score": 0.95},
        {"chunk_id": doc_b, "content": "Doc B", "document_id": uuid.uuid4(), "document_name": "b.pdf", "chunk_type": "text", "score": 0.80},
    ]

    sparse_results = [
        {"chunk_id": doc_b, "content": "Doc B", "document_id": uuid.uuid4(), "document_name": "b.pdf", "chunk_type": "text", "score": 0.90},
        {"chunk_id": doc_c, "content": "Doc C", "document_id": uuid.uuid4(), "document_name": "c.pdf", "chunk_type": "text", "score": 0.85},
    ]

    fused = hybrid_search_service._apply_rrf(dense_results, sparse_results)
    assert len(fused) == 3

    # Doc B está en posición 2 en densa y 1 en esparsa -> debe tener mayor RRF que Doc A (solo en densa)
    # RRF(B) = 1/(60+2) + 1/(60+1) = 0.016129 + 0.016393 = 0.032522
    # RRF(A) = 1/(60+1) = 0.016393
    assert fused[0]["chunk_id"] == doc_b
    assert fused[0]["score"] > fused[1]["score"]


@pytest.mark.asyncio
async def test_search_endpoint_validation():
    """Verifica la validación de parámetros en el endpoint /api/v1/search."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Consulta vacía
        resp = await client.post("/api/v1/search", json={"query": ""})
        assert resp.status_code == 422

        # Modo inválido
        resp = await client.post("/api/v1/search", json={"query": "test", "mode": "invalid_mode"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_endpoint_hybrid():
    """Verifica que el endpoint /api/v1/search responda con la estructura de esquema esperada y rerank_score."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "balance financiero y facturas",
            "top_k": 3,
            "mode": "hybrid",
            "include_parent": True,
            "rerank": True,
        }
        resp = await client.post("/api/v1/search", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "balance financiero y facturas"
        assert data["mode"] == "hybrid"
        assert "total_results" in data
        assert "results" in data
        assert isinstance(data["results"], list)
        for item in data["results"]:
            assert "rerank_score" in item


@pytest.mark.asyncio
async def test_search_endpoint_with_rerank_disabled():
    """Verifica que el endpoint /api/v1/search funcione correctamente con rerank=False."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "auditoría de sistemas",
            "top_k": 2,
            "mode": "dense",
            "include_parent": False,
            "rerank": False,
        }
        resp = await client.post("/api/v1/search", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "dense"
        assert isinstance(data["results"], list)

