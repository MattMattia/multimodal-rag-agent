import asyncio
import hashlib
import logging
import math
from typing import List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Intentar importar el SDK moderno oficial google-genai
_USE_MODERN_GENAI = False
try:
    from google import genai
    from google.genai import types
    _USE_MODERN_GENAI = True
except ImportError:
    pass


class EmbeddingService:
    """Servicio para generar representaciones vectoriales densas (embeddings) con text-embedding-004."""

    def __init__(self):
        self.model_name = "text-embedding-004"
        self.dimension = 768
        self.api_key = settings.GOOGLE_API_KEY
        self._client = None
        self._initialized = False

    def _ensure_client(self):
        """Inicializa o actualiza el cliente de Gemini si la API key se configuró dinámicamente."""
        import os
        current_key = os.getenv("GOOGLE_API_KEY") or settings.GOOGLE_API_KEY
        if current_key and current_key != "tu_google_api_key_aqui" and (not self._initialized or self.api_key != current_key):
            self.api_key = current_key
            if _USE_MODERN_GENAI:
                try:
                    self._client = genai.Client(api_key=self.api_key)
                    self._initialized = True
                    logger.info("EmbeddingService configurado con %s (dim: %d)", self.model_name, self.dimension)
                except Exception as e:
                    logger.error("Error al inicializar cliente de embeddings: %s", e)

    def _generate_mock_embedding(self, text: str) -> List[float]:
        """Genera un vector unitario determinístico de 768 dimensiones basado en el hash del texto.

        Permite ejecutar pruebas unitarias y desarrollo local sin agotar cuota ni fallar sin internet.
        """
        vector = []
        for i in range(self.dimension):
            # Combinación de hash SHA-256 con índice para producir valores pseudo-aleatorios estables
            h = hashlib.sha256(f"{text}_{i}".encode("utf-8")).digest()
            val = (int.from_bytes(h[:4], "big") / 2**32) - 0.5
            vector.append(val)

        # Normalización euclídea (L2) para que el producto punto equivalga a similitud de coseno
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [round(x / norm, 6) for x in vector]

    async def get_embedding(self, text: str) -> List[float]:
        """Obtiene el embedding de un texto individual."""
        if not text or not text.strip():
            return [0.0] * self.dimension

        self._ensure_client()

        if not self._initialized or not self._client:
            return self._generate_mock_embedding(text)

        try:
            response = await self._client.aio.models.embed_content(
                model=self.model_name,
                contents=text,
            )
            # Manejar respuesta individual del SDK
            if hasattr(response, "embedding") and response.embedding:
                return response.embedding.values
            elif hasattr(response, "embeddings") and response.embeddings:
                return response.embeddings[0].values
            return self._generate_mock_embedding(text)
        except Exception as e:
            logger.error("Error en API de embeddings para texto individual: %s", e)
            return self._generate_mock_embedding(text)

    async def get_embeddings_batch(
        self, texts: List[str], batch_size: int = 50
    ) -> List[List[float]]:
        """Genera embeddings en lotes para optimizar llamadas a la API."""
        if not texts:
            return []

        self._ensure_client()

        if not self._initialized or not self._client:
            return [self._generate_mock_embedding(t) for t in texts]

        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = await self._client.aio.models.embed_content(
                    model=self.model_name,
                    contents=batch,
                )
                if hasattr(response, "embeddings") and response.embeddings:
                    for emb in response.embeddings:
                        all_embeddings.append(emb.values)
                else:
                    logger.warning("Respuesta de batch sin 'embeddings', usando fallback para lote.")
                    all_embeddings.extend([self._generate_mock_embedding(t) for t in batch])
            except Exception as e:
                logger.error("Error en API de embeddings para lote %d-%d: %s", i, i + len(batch), e)
                # Fallback seguro para no detener la ingesta
                all_embeddings.extend([self._generate_mock_embedding(t) for t in batch])

        return all_embeddings


embedding_service = EmbeddingService()

