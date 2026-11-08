import asyncio
import hashlib
import logging
import math

from app.core.config import settings

logger = logging.getLogger(__name__)

# Backoff exponencial entre reintentos ante errores transitorios (429/503/timeouts)
RETRY_BACKOFF_SECONDS = (0.5, 1.0, 2.0)

# Intentar importar el SDK moderno oficial google-genai
_USE_MODERN_GENAI = False
try:
    from google import genai
    from google.genai import types as genai_types
    _USE_MODERN_GENAI = True
except ImportError:
    genai_types = None  # type: ignore[assignment]


def _l2_normalize(values) -> list[float]:
    """gemini-embedding-001 only returns unit vectors at 3072 dims; truncated outputs must be normalized."""
    vector = [float(x) for x in values]
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else vector


class EmbeddingService:
    """Servicio para generar representaciones vectoriales densas (embeddings) con Gemini Embedding."""

    def __init__(self):
        self.model_name = settings.GEMINI_EMBEDDING_MODEL
        self.dimension = settings.EMBEDDING_DIMENSION
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

    def _generate_mock_embedding(self, text: str) -> list[float]:
        """Genera un vector unitario determinístico de 768 dimensiones basado en el hash del texto.

        Permite ejecutar pruebas unitarias y desarrollo local sin agotar cuota ni fallar sin internet.
        """
        vector = []
        for i in range(self.dimension):
            # Combinación de hash SHA-256 con índice para producir valores pseudo-aleatorios estables
            h = hashlib.sha256(f"{text}_{i}".encode()).digest()
            val = (int.from_bytes(h[:4], "big") / 2**32) - 0.5
            vector.append(val)

        # Normalización euclídea (L2) para que el producto punto equivalga a similitud de coseno
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [round(x / norm, 6) for x in vector]

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        """Errores recuperables con reintento: 429/503, saturación de cuota y timeouts."""
        if isinstance(exc, TimeoutError):  # en Python 3.11 asyncio.TimeoutError es TimeoutError
            return True
        if getattr(exc, "code", None) in (429, 503) or getattr(exc, "status_code", None) in (429, 503):
            return True
        text = str(exc)
        if any(marker in text for marker in ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")):
            return True
        return "timeout" in text.lower() or "timed out" in text.lower()

    def _embed_config(self):
        """Requests EMBEDDING_DIMENSION so vectors fit the vector(768) column (the model defaults to 3072)."""
        return genai_types.EmbedContentConfig(output_dimensionality=self.dimension)

    async def _embed_with_retry(self, contents):
        """Llama a la API de embeddings con hasta 3 reintentos (backoff 0.5s, 1s, 2s) ante errores transitorios.

        Si el error persiste (o no es transitorio) se propaga: jamás se sustituye por vectores falsos
        cuando hay una API key real, para no contaminar el índice vectorial.
        """
        attempt = 0
        while True:
            try:
                return await self._client.aio.models.embed_content(
                    model=self.model_name, contents=contents, config=self._embed_config()
                )
            except Exception as e:
                if attempt >= len(RETRY_BACKOFF_SECONDS) or not self._is_transient(e):
                    logger.error("Error en API de embeddings (intento %d): %s", attempt + 1, e)
                    raise
                delay = RETRY_BACKOFF_SECONDS[attempt]
                logger.warning("Error transitorio en embeddings (%s). Reintento %d en %.1fs", e, attempt + 1, delay)
                await asyncio.sleep(delay)
                attempt += 1

    async def get_embedding(self, text: str) -> list[float]:
        """Obtiene el embedding de un texto individual."""
        if not text or not text.strip():
            return [0.0] * self.dimension

        self._ensure_client()

        # Modo demo/offline/test: sin cliente configurado se usan vectores determinísticos
        if not self._initialized or not self._client:
            return self._generate_mock_embedding(text)

        response = await self._embed_with_retry(text)
        if hasattr(response, "embedding") and response.embedding:
            return _l2_normalize(response.embedding.values)
        if hasattr(response, "embeddings") and response.embeddings:
            return _l2_normalize(response.embeddings[0].values)
        raise RuntimeError("La API de embeddings devolvió una respuesta sin vectores.")

    async def get_embeddings_batch(
        self, texts: list[str], batch_size: int | None = None
    ) -> list[list[float]]:
        """Genera embeddings en lotes para optimizar llamadas a la API."""
        if not texts:
            return []

        batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self._ensure_client()

        if not self._initialized or not self._client:
            return [self._generate_mock_embedding(t) for t in texts]

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self._embed_with_retry(batch)
            if not (hasattr(response, "embeddings") and response.embeddings):
                raise RuntimeError("La API de embeddings devolvió un lote sin vectores.")
            all_embeddings.extend(_l2_normalize(emb.values) for emb in response.embeddings)

        return all_embeddings


embedding_service = EmbeddingService()

