"""Limitador de tasa en memoria (ventana deslizante por IP) como middleware ASGI.

Pensado para una sola instancia de la API (demo/portafolio): el estado vive en el proceso.
La IP es la del socket (`scope["client"]`); no se confía en `X-Forwarded-For` porque es falsificable.
"""

import math
import os
import sys
import time
from collections import deque
from collections.abc import Callable

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings

WINDOW_SECONDS = 60.0
EXEMPT_PATHS = frozenset({"/health", "/api/v1/health"})
_SWEEP_EVERY = 1024  # cada N comprobaciones se purgan las IPs inactivas


def is_running_under_pytest() -> bool:
    return "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ


class SlidingWindowRateLimiter:
    """Cuenta peticiones por clave dentro de los últimos `WINDOW_SECONDS` segundos."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._checks = 0

    def check(self, key: str, limit: int) -> tuple[bool, int]:
        """Registra una petición. Devuelve (permitida, segundos_hasta_poder_reintentar)."""
        now = self._clock()
        self._checks += 1
        if self._checks % _SWEEP_EVERY == 0:
            self._sweep(now)

        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - WINDOW_SECONDS:
            hits.popleft()

        if len(hits) >= limit:
            return False, max(1, math.ceil(hits[0] + WINDOW_SECONDS - now))
        hits.append(now)
        return True, 0

    def _sweep(self, now: float) -> None:
        stale = [k for k, h in self._hits.items() if not h or h[-1] <= now - WINDOW_SECONDS]
        for key in stale:
            del self._hits[key]

    def reset(self) -> None:
        self._hits.clear()
        self._checks = 0


rate_limiter = SlidingWindowRateLimiter()


def _is_active() -> bool:
    return bool(settings.RATE_LIMIT_ENABLED) and not is_running_under_pytest()


class RateLimitMiddleware:
    """Middleware ASGI que responde 429 + `Retry-After` al superar `RATE_LIMIT_PER_MINUTE` por IP."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _is_active() or scope.get("path") in EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        allowed, retry_after = rate_limiter.check(client[0] if client else "unknown", settings.RATE_LIMIT_PER_MINUTE)
        if allowed:
            await self.app(scope, receive, send)
            return

        response = JSONResponse(
            status_code=429,
            content={"detail": "Demasiadas solicitudes. Inténtalo de nuevo más tarde."},
            headers={"Retry-After": str(retry_after)},
        )
        await response(scope, receive, send)
