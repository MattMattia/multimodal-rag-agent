"""In-memory sliding-window rate limiter (AUDIT-06): unit behavior and middleware integration."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.rate_limit import SlidingWindowRateLimiter, rate_limiter
from app.main import app


class _Clock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


# ---------------------------------------------------------------------------
# Unit: SlidingWindowRateLimiter
# ---------------------------------------------------------------------------
def test_limiter_blocks_after_limit_and_reports_retry_after():
    clock = _Clock()
    limiter = SlidingWindowRateLimiter(clock=clock)
    assert [limiter.check("1.1.1.1", 3)[0] for _ in range(3)] == [True, True, True]
    allowed, retry_after = limiter.check("1.1.1.1", 3)
    assert allowed is False
    assert retry_after == 60


def test_limiter_window_slides_instead_of_resetting_in_blocks():
    clock = _Clock(0.0)
    limiter = SlidingWindowRateLimiter(clock=clock)
    assert limiter.check("ip", 2)[0] is True  # t=0
    clock.now = 30.0
    assert limiter.check("ip", 2)[0] is True  # t=30
    clock.now = 59.0
    allowed, retry_after = limiter.check("ip", 2)
    assert (allowed, retry_after) == (False, 1)  # first request leaves the window at t=60
    clock.now = 60.5
    assert limiter.check("ip", 2)[0] is True  # t=0 expired, t=30 still counts
    clock.now = 61.0
    assert limiter.check("ip", 2)[0] is False  # t=30 and t=60.5 in window


def test_limiter_tracks_each_ip_independently_and_reset_clears_state():
    limiter = SlidingWindowRateLimiter(clock=_Clock())
    assert limiter.check("a", 1)[0] is True
    assert limiter.check("a", 1)[0] is False
    assert limiter.check("b", 1)[0] is True
    limiter.reset()
    assert limiter.check("a", 1)[0] is True


# ---------------------------------------------------------------------------
# Integration: middleware
# ---------------------------------------------------------------------------
@pytest.fixture
def http():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def limiting_on(monkeypatch):
    """Activate limiting (it is auto-disabled under pytest) with a tiny quota and a clean limiter."""
    monkeypatch.setattr("app.core.rate_limit.is_running_under_pytest", lambda: False)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.mark.asyncio
async def test_middleware_returns_429_with_retry_after(limiting_on, http):
    async with http as client:
        first = await client.get("/")
        second = await client.get("/")
        third = await client.get("/")
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert 1 <= int(third.headers["retry-after"]) <= 60
    assert "detail" in third.json()


@pytest.mark.asyncio
async def test_health_endpoints_are_exempt(limiting_on, http):
    async with http as client:
        for _ in range(5):
            assert (await client.get("/health")).status_code == 200
            assert (await client.get("/api/v1/health")).status_code in (200, 503)
        # Exempt calls do not consume quota for other routes either.
        assert (await client.get("/")).status_code == 200


@pytest.mark.asyncio
async def test_disabled_by_setting(limiting_on, http, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)
    async with http as client:
        statuses = [(await client.get("/")).status_code for _ in range(5)]
    assert statuses == [200] * 5


@pytest.mark.asyncio
async def test_disabled_automatically_under_pytest(http, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)
    rate_limiter.reset()
    async with http as client:
        statuses = [(await client.get("/")).status_code for _ in range(4)]
    assert statuses == [200] * 4
