import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.reranker import RerankerService, reranker_service


def test_reranker_empty_list():
    """Valida que una lista vacía de candidatos retorne lista vacía inmediatamente."""
    service = RerankerService()
    loop = asyncio.new_event_loop()
    res = loop.run_until_complete(service.rerank(query="consulta", candidates=[]))
    assert res == []


def test_reranker_single_candidate():
    """Valida que un único candidato preserve sus datos y reciba un rerank_score."""
    service = RerankerService()
    candidate = {
        "chunk_id": uuid.uuid4(),
        "content": "Experiencia en Python y FastAPI",
        "document_name": "cv.pdf",
        "score": 0.85,
    }
    loop = asyncio.new_event_loop()
    res = loop.run_until_complete(service.rerank(query="Python", candidates=[candidate], top_n=2))
    assert len(res) == 1
    assert res[0]["content"] == candidate["content"]
    assert "rerank_score" in res[0]
    assert res[0]["rerank_score"] == 0.85


@pytest.mark.asyncio
async def test_reranker_deterministic_fallback_on_exception():
    """Valida que ante fallo de la API o timeout se preserve el ordenamiento RRF original sin lanzar excepciones."""
    service = RerankerService()

    cand1 = {"chunk_id": uuid.uuid4(), "content": "Texto 1", "score": 0.032}
    cand2 = {"chunk_id": uuid.uuid4(), "content": "Texto 2", "score": 0.016}
    cand3 = {"chunk_id": uuid.uuid4(), "content": "Texto 3", "score": 0.008}
    candidates = [cand1, cand2, cand3]

    # Forzar excepción en _score_with_gemini
    with patch.object(service, "_score_with_gemini", side_effect=TimeoutError("Timeout simulado de Gemini")):
        with patch.object(service, "_ensure_client", return_value=True):
            service._client = MagicMock()
            result = await service.rerank(query="consulta", candidates=candidates, top_n=2)

    assert len(result) == 2
    # El orden debe conservarse idéntico al original
    assert result[0]["chunk_id"] == cand1["chunk_id"]
    assert result[1]["chunk_id"] == cand2["chunk_id"]
    assert result[0]["rerank_score"] == 0.032
    assert result[1]["rerank_score"] == 0.016


@pytest.mark.asyncio
async def test_reranker_successful_reordering():
    """Valida que el Reranker reordene correctamente los candidatos en función del puntaje devuelto por Gemini."""
    service = RerankerService()

    # cand1 estaba primero en RRF pero cand2 es más relevante semánticamente
    cand1 = {"chunk_id": uuid.uuid4(), "content": "Información general sobre clima", "score": 0.030}
    cand2 = {"chunk_id": uuid.uuid4(), "content": "Detalles del balance financiero y facturación", "score": 0.015}
    candidates = [cand1, cand2]

    # Simular respuesta de Gemini donde el índice 1 (cand2) obtiene mayor score que el índice 0 (cand1)
    mock_scored = [
        {**cand2, "rerank_score": 0.95},
        {**cand1, "rerank_score": 0.20},
    ]

    with patch.object(service, "_score_with_gemini", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = mock_scored
        with patch.object(service, "_ensure_client", return_value=True):
            service._client = MagicMock()
            result = await service.rerank(
                query="balance y facturas",
                candidates=candidates,
                top_n=2,
            )

    assert len(result) == 2
    # cand2 debe quedar primero debido a su mayor rerank_score
    assert result[0]["chunk_id"] == cand2["chunk_id"]
    assert result[0]["rerank_score"] == 0.95
    assert result[1]["chunk_id"] == cand1["chunk_id"]
    assert result[1]["rerank_score"] == 0.20


def test_parse_scoring_json_formats():
    """Valida la extracción robusta del mapa de scores con JSON estándar y bloques markdown."""
    service = RerankerService()

    # Caso 1: JSON puro
    raw1 = '[{"index": 0, "score": 0.88}, {"index": 1, "score": 0.45}]'
    res1 = service._parse_scoring_json(raw1)
    assert res1 == {0: 0.88, 1: 0.45}

    # Caso 2: Bloque markdown ```json
    raw2 = '```json\n[{"index": 0, "score": 0.99}, {"index": 1, "score": 0.12}]\n```'
    res2 = service._parse_scoring_json(raw2)
    assert res2 == {0: 0.99, 1: 0.12}

    # Caso 3: Texto con JSON embebido y notas
    raw3 = 'Aquí tienes la evaluación solicitada:\n[{"index": 0, "score": 0.75}]'
    res3 = service._parse_scoring_json(raw3)
    assert res3 == {0: 0.75}

