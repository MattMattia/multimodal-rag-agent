import contextlib
import logging
import os
import time
from typing import Any, Dict, Generator, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Intento de importación de Langfuse SDK
_LANGFUSE_AVAILABLE = False
try:
    from langfuse import Langfuse
    _LANGFUSE_AVAILABLE = True
except ImportError:
    pass


class DummySpan:
    """Span simulado no-op para cuando Langfuse está deshabilitado o no responde."""

    def __init__(self, name: str = "dummy_span", id: str = "dummy_id"):
        self.name = name
        self.id = id
        self.trace_id = "dummy_trace_id"

    def end(self, *args, **kwargs) -> None:
        pass

    def update(self, *args, **kwargs) -> None:
        pass

    def span(self, *args, **kwargs) -> "DummySpan":
        return DummySpan()

    def generation(self, *args, **kwargs) -> "DummySpan":
        return DummySpan()

    def event(self, *args, **kwargs) -> None:
        pass

    def start_observation(self, *args, **kwargs) -> "DummySpan":
        return DummySpan()

    def __enter__(self) -> "DummySpan":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class DummyTrace:
    """Traza simulada no-op que previene errores y llamadas nulas sin degradar el rendimiento."""

    def __init__(self, name: str = "dummy_trace", id: str = "dummy_id"):
        self.name = name
        self.id = id
        self.trace_id = "dummy_trace_id"

    def span(self, *args, **kwargs) -> DummySpan:
        return DummySpan()

    def generation(self, *args, **kwargs) -> DummySpan:
        return DummySpan()

    def event(self, *args, **kwargs) -> None:
        pass

    def update(self, *args, **kwargs) -> None:
        pass

    def end(self, *args, **kwargs) -> None:
        pass

    def start_observation(self, *args, **kwargs) -> DummySpan:
        return DummySpan()

    def __enter__(self) -> "DummyTrace":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class TelemetryService:
    """Servicio singleton para observabilidad y telemetría de LLM/RAG con Langfuse.

    Garantiza inicialización no bloqueante y graceful fallback en todo momento.
    """

    def __init__(self):
        self._client: Optional[Any] = None
        self._enabled = False
        self._initialized = False
        self._init_client()

    def _init_client(self) -> bool:
        """Inicializa de forma segura el cliente Langfuse verificando variables de entorno y estado."""
        enabled = (
            os.environ.get("LANGFUSE_ENABLED", "").lower() in ("1", "true", "yes")
            or settings.LANGFUSE_ENABLED
        )
        public_key = (
            os.environ.get("LANGFUSE_PUBLIC_KEY")
            or settings.LANGFUSE_PUBLIC_KEY
            or ""
        ).strip()
        secret_key = (
            os.environ.get("LANGFUSE_SECRET_KEY")
            or settings.LANGFUSE_SECRET_KEY
            or ""
        ).strip()
        host = (
            os.environ.get("LANGFUSE_HOST")
            or settings.LANGFUSE_HOST
            or "http://localhost:3000"
        ).strip()

        if not enabled:
            self._enabled = False
            self._client = None
            return False

        if not _LANGFUSE_AVAILABLE:
            logger.warning("LANGFUSE_ENABLED=true pero la biblioteca 'langfuse' no está instalada.")
            self._enabled = False
            return False

        if not public_key or not secret_key:
            logger.info("Langfuse habilitado pero no se encontraron credenciales válidas. Modo inactivo.")
            self._enabled = False
            return False

        try:
            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
            self._enabled = True
            self._initialized = True
            logger.info("TelemetryService inicializado correctamente con Langfuse en %s", host)
            return True
        except Exception as e:
            logger.warning("Error al inicializar cliente Langfuse (%s: %s). Modo contingencia activo.", type(e).__name__, e)
            self._client = None
            self._enabled = False
            return False

    @property
    def is_enabled(self) -> bool:
        return self._enabled and self._client is not None

    def start_trace(
        self,
        name: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        input: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Any:
        if not self.is_enabled or not self._client:
            return DummyTrace(name=name, id=session_id or "local")

        meta = dict(metadata or {})
        try:
            if hasattr(self._client, "trace"):
                return self._client.trace(
                    name=name,
                    session_id=str(session_id) if session_id else None,
                    user_id=str(user_id) if user_id else None,
                    input=input,
                    metadata=meta,
                    tags=tags or [],
                )
            elif hasattr(self._client, "start_observation"):
                return self._client.start_observation(
                    name=name,
                    as_type="agent",
                    input=input,
                    metadata=meta,
                )
        except Exception as e:
            logger.warning("Error iniciando traza en Langfuse: %s", e)

        return DummyTrace(name=name, id=session_id or "local")

    @contextlib.contextmanager
    def span(
        self,
        parent: Optional[Any],
        name: str,
        span_type: str = "span",
        input: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Generator[Any, None, None]:
        """Context manager para instrumentar spans de ejecución registrando automáticamente latencia."""
        start_time = time.time()
        span_obj = None

        if self.is_enabled and not isinstance(parent, (DummyTrace, DummySpan)):
            try:
                # Si el padre soporta span (Langfuse v2/v3)
                if parent and hasattr(parent, "span"):
                    span_obj = parent.span(
                        name=name,
                        input=input,
                        metadata=metadata or {},
                    )
                # Si el padre soporta start_observation (Langfuse v4)
                elif parent and hasattr(parent, "start_observation"):
                    span_obj = parent.start_observation(
                        name=name,
                        as_type=span_type if span_type in ("span", "tool", "chain", "agent", "retriever") else "span",
                        input=input,
                        metadata=metadata or {},
                    )
                # Si no hay padre pero el cliente soporta span directo (Langfuse v2)
                elif parent is None and hasattr(self._client, "span"):
                    span_obj = self._client.span(
                        name=name,
                        input=input,
                        metadata=metadata or {},
                    )
                # Si no hay padre pero el cliente soporta start_observation (v4)
                elif parent is None and hasattr(self._client, "start_observation"):
                    span_obj = self._client.start_observation(
                        name=name,
                        as_type=span_type if span_type in ("span", "tool", "chain", "agent", "retriever") else "span",
                        input=input,
                        metadata=metadata or {},
                    )
            except Exception as e:
                logger.debug("Error creando span '%s' en Langfuse: %s", name, e)
                span_obj = None

        if span_obj is None:
            span_obj = DummySpan(name)

        try:
            yield span_obj
        finally:
            elapsed = time.time() - start_time
            if span_obj and hasattr(span_obj, "end"):
                try:
                    span_obj.end(metadata={"latency_seconds": round(elapsed, 4), **(metadata or {})})
                except Exception as e:
                    logger.debug("Error finalizando span '%s': %s", name, e)

    def record_generation(
        self,
        parent: Optional[Any],
        name: str,
        model: str,
        input: Any,
        output: Any,
        usage: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Registra un evento de generación LLM con modelo, consumo de tokens y prompts."""
        if not self.is_enabled:
            return DummySpan(name)

        try:
            # Langfuse v2/v3: parent.generation
            if parent and hasattr(parent, "generation") and not isinstance(parent, (DummyTrace, DummySpan)):
                return parent.generation(
                    name=name,
                    model=model,
                    input=input,
                    output=output,
                    usage=usage,
                    metadata=metadata or {},
                )
            # Langfuse v4: start_observation as_type="generation"
            elif parent and hasattr(parent, "start_observation") and not isinstance(parent, (DummyTrace, DummySpan)):
                gen = parent.start_observation(
                    name=name,
                    as_type="generation",
                    model=model,
                    input=input,
                    output=output,
                    usage_details=usage,
                    metadata=metadata or {},
                )
                if hasattr(gen, "end"):
                    gen.end()
                return gen
        except Exception as e:
            logger.debug("Error registrando generación en Langfuse: %s", e)

        return DummySpan(name)

    def flush(self) -> None:
        """Envía de forma no bloqueante las trazas pendientes al servidor de Langfuse."""
        if self.is_enabled and self._client and hasattr(self._client, "flush"):
            try:
                self._client.flush()
            except Exception as e:
                logger.debug("Error al ejecutar flush en Langfuse: %s", e)


telemetry_service = TelemetryService()
