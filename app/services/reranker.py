import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.telemetry import telemetry_service

logger = logging.getLogger(__name__)

# Intentar importar el SDK moderno de Google GenAI
_USE_MODERN_GENAI = False
try:
    from google import genai
    from google.genai import types
    _USE_MODERN_GENAI = True
except ImportError:
    pass


class RerankerService:
    """Servicio de Reranking Semántico que evalúa y refina la relevancia contextual de fragmentos

    recuperados mediante RRF (Reciprocal Rank Fusion) utilizando modelos generativos de Gemini.
    """

    def __init__(self):
        self.model_name = settings.GEMINI_AGENT_MODEL
        self.api_key = settings.GOOGLE_API_KEY
        self._client = None
        self._working_model: Optional[str] = None
        self._ensure_client()

    def _ensure_client(self) -> bool:
        """Verifica e inicializa el cliente del SDK google-genai si la clave es válida."""
        current_key = (
            os.environ.get("GOOGLE_API_KEY") or settings.GOOGLE_API_KEY or ""
        ).strip()
        if (
            _USE_MODERN_GENAI
            and current_key
            and current_key != "tu_google_api_key_aqui"
            and not current_key.startswith("tu_google")
        ):
            if not self._client or self.api_key != current_key:
                try:
                    self.api_key = current_key
                    self._client = genai.Client(api_key=self.api_key)
                    logger.info("RerankerService inicializado con cliente google-genai.")
                except Exception as e:
                    logger.error("Error al inicializar genai.Client en RerankerService: %s", e)
                    self._client = None
            return self._client is not None
        return False

    async def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_n: int = 4,
    ) -> List[Dict[str, Any]]:
        """Reordena semánticamente una lista de fragmentos candidatos respecto a la consulta.

        Args:
            query: Consulta o pregunta del usuario.
            candidates: Lista de fragmentos candidatos (con content, document_name, score, etc.).
            top_n: Cantidad máxima de fragmentos a retornar tras el reordenamiento.

        Returns:
            Lista de fragmentos refinados ordenados por `rerank_score` descendente (máximo top_n).
        """
        if not candidates:
            return []

        with telemetry_service.span(
            parent=None,
            name="semantic_reranker",
            span_type="chain",
            input={"query": query, "candidate_count": len(candidates), "top_n": top_n},
        ) as rerank_span:
            if len(candidates) <= 1:
                res = [dict(candidates[0])]
                res[0]["rerank_score"] = round(float(res[0].get("score", 1.0)), 4)
                rerank_span.update(output={"returned_count": len(res), "mode": "single_candidate"})
                return res

            # Si el cliente no está disponible, aplicar inmediatamente el fallback determinístico
            client_ready = self._ensure_client()
            if not client_ready or not self._client:
                result = self._apply_deterministic_fallback(candidates, top_n)
                rerank_span.update(output={"returned_count": len(result), "mode": "fallback"})
                return result

            try:
                # Ejecutar con timeout de 8 segundos para evitar bloqueos
                result = await asyncio.wait_for(
                    self._score_with_gemini(query=query, candidates=candidates, top_n=top_n),
                    timeout=settings.RERANK_TIMEOUT_SECONDS,
                )
                rerank_span.update(output={"returned_count": len(result), "mode": "gemini_scoring"})
                return result
            except Exception as e:
                logger.warning(
                    "RerankerService: Falló la evaluación semántica con Gemini (%s: %s). Aplicando fallback determinístico RRF.",
                    type(e).__name__,
                    e,
                )
                result = self._apply_deterministic_fallback(candidates, top_n)
                rerank_span.update(output={"returned_count": len(result), "mode": "fallback_error"})
                return result

    async def _score_with_gemini(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_n: int,
    ) -> List[Dict[str, Any]]:
        """Envía los fragmentos a Gemini para calificar su relevancia semántica de 0.0 a 1.0."""
        chunks_text = []
        for idx, c in enumerate(candidates):
            content_snippet = (c.get("content") or "")[: settings.RERANK_MAX_SNIPPET_CHARS].strip().replace("\n", " ")
            doc_name = c.get("document_name", "documento")
            chunks_text.append(f"[{idx}] ({doc_name}): {content_snippet}")

        formatted_chunks = "\n".join(chunks_text)

        prompt = f"""Evalúa la relevancia semántica de los siguientes fragmentos de texto respecto a la consulta del usuario.
Asigna a cada fragmento una puntuación numérica entre 0.0 (completamente irrelevante) y 1.0 (altamente relevante y responde a la consulta).

Consulta del usuario: "{query}"

Fragmentos candidatos:
{formatted_chunks}

Instrucciones estrictas:
Responde ÚNICAMENTE con un JSON en formato de lista de objetos donde cada objeto contenga:
- "index": el índice entero del fragmento ([0], [1], etc.)
- "score": la puntuación de relevancia asignada (número flotante entre 0.0 y 1.0)

Ejemplo de respuesta esperada:
[
  {{"index": 0, "score": 0.95}},
  {{"index": 1, "score": 0.20}}
]
"""
        candidate_models = [
            self._working_model or self.model_name,
            "gemini-3.8-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ]

        seen = set()
        unique_models = []
        for m in candidate_models:
            if m and m not in seen:
                seen.add(m)
                unique_models.append(m)

        raw_response_text = ""
        last_exc = None

        for model in unique_models:
            try:
                config = types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                )
                resp = await self._client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                if resp.text:
                    raw_response_text = resp.text.strip()
                    self._working_model = model
                    break
            except Exception as e:
                last_exc = e
                logger.debug("RerankerService: Modelo '%s' no respondió: %s", model, e)
                continue

        if not raw_response_text:
            raise RuntimeError(f"Ningún modelo de Gemini pudo evaluar los candidatos. Último error: {last_exc}")

        # Parsear respuesta JSON
        scores_map = self._parse_scoring_json(raw_response_text)

        scored_candidates = []
        for idx, c in enumerate(candidates):
            item_copy = dict(c)
            assigned_score = scores_map.get(idx)
            if assigned_score is None:
                # Si algún fragmento no fue puntuado en el JSON, asignar penalización suave sobre su score original
                assigned_score = max(0.05, min(1.0, float(c.get("score", 0.5)) * 0.9))
            item_copy["rerank_score"] = round(float(assigned_score), 4)
            scored_candidates.append(item_copy)

        # Ordenar por rerank_score descendente; si empatan, desempatar por el score RRF previo
        scored_candidates.sort(
            key=lambda item: (item.get("rerank_score", 0.0), float(item.get("score", 0.0))),
            reverse=True,
        )

        return scored_candidates[:top_n]

    def _parse_scoring_json(self, raw_text: str) -> Dict[int, float]:
        """Extrae el mapa index -> score del texto retornado por el LLM."""
        clean_text = raw_text.strip()
        # Remover bloques de código markdown si existen
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
            clean_text = re.sub(r"\s*```$", "", clean_text)

        scores_map: Dict[int, float] = {}
        try:
            parsed = json.loads(clean_text)
            if isinstance(parsed, list):
                for elem in parsed:
                    if isinstance(elem, dict) and "index" in elem and "score" in elem:
                        idx = int(elem["index"])
                        score = max(0.0, min(1.0, float(elem["score"])))
                        scores_map[idx] = score
        except Exception:
            # Búsqueda por expresión regular si el JSON venía truncado o con texto extra
            matches = re.findall(r'\{\s*"index"\s*:\s*(\d+)\s*,\s*"score"\s*:\s*([0-9.]+)\s*\}', raw_text)
            for m_idx, m_score in matches:
                try:
                    scores_map[int(m_idx)] = max(0.0, min(1.0, float(m_score)))
                except Exception:
                    pass

        return scores_map

    def _apply_deterministic_fallback(
        self,
        candidates: List[Dict[str, Any]],
        top_n: int,
    ) -> List[Dict[str, Any]]:
        """Fallback determinístico que preserva el ordenamiento original RRF y calcula un rerank_score normalizado."""
        results = []
        for idx, c in enumerate(candidates[:top_n]):
            item_copy = dict(c)
            # Conservar el orden RRF. Si viene score previo, usarlo; de lo contrario asignar decaimiento por ranking
            orig_score = float(c.get("score", 1.0 / (idx + 1)))
            item_copy["rerank_score"] = round(orig_score, 4)
            results.append(item_copy)
        return results


reranker_service = RerankerService()

