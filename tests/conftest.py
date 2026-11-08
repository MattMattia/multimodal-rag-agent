"""Shared pytest fixtures for the whole test suite.

SQLite mode: run the whole suite against a throw-away SQLite file instead of PostgreSQL with

    TEST_DATABASE_URL=sqlite+aiosqlite:///<path>/test_rag.db python -m pytest -q -p no:cacheprovider

Tests marked ``@pytest.mark.postgres_only`` (pg_indexes / DDL / pool introspection) are skipped in that mode.
"""

import os
from pathlib import Path

import pytest
import pytest_asyncio

# Must run before anything imports app.core.config / app.core.database (the engine is built at import time).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
SQLITE_MODE = TEST_DATABASE_URL.startswith("sqlite")
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL


def pytest_collection_modifyitems(config, items):
    if not SQLITE_MODE:
        return
    skip = pytest.mark.skip(reason="PostgreSQL-only test (skipped in SQLite mode)")
    for item in items:
        if "postgres_only" in item.keywords:
            item.add_marker(skip)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def sqlite_mode_schema():
    """In SQLite mode start from an empty file and create the schema once (PostgreSQL keeps its existing schema)."""
    if not SQLITE_MODE:
        yield
        return
    from app.core import database

    db_file = Path(database.engine.url.database or "")
    if db_file.name:
        db_file.unlink(missing_ok=True)
    await database.create_schema(database.engine)
    yield
    await database.engine.dispose()
    if db_file.name:
        db_file.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def inert_langfuse(monkeypatch):
    """Never let a developer .env with LANGFUSE_ENABLED=true make tests flush traces to an unreachable server."""
    from app.core.telemetry import telemetry_service

    monkeypatch.setattr(telemetry_service, "_enabled", False)


@pytest.fixture(autouse=True)
def no_background_side_effects(monkeypatch):
    """Tests opt in to auto-seeding and SQLite fallback explicitly."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "AUTO_SEED_DEMO_CORPUS", False)
    monkeypatch.setattr(settings, "AUTO_FALLBACK_SQLITE", False)


@pytest_asyncio.fixture
async def sqlite_db(tmp_path):
    """Rebind the app (engine + AsyncSessionLocal) to an isolated, empty SQLite file for one test."""
    from app.core import database

    previous = database.engine
    new_engine = database.build_engine(f"sqlite+aiosqlite:///{(tmp_path / 'isolated.db').as_posix()}")
    database.bind_engine(new_engine)
    await database.create_schema(new_engine)
    try:
        yield new_engine
    finally:
        database.bind_engine(previous)
        await new_engine.dispose()


@pytest.fixture
def demo_dirs(tmp_path, monkeypatch):
    """Point the Golden Corpus generator and the file endpoints to isolated upload directories."""
    documents, images = tmp_path / "uploads" / "documents", tmp_path / "uploads" / "images"
    for module in ("app.services.demo_seeder", "app.api.v1.endpoints.files"):
        monkeypatch.setattr(f"{module}.DOCUMENTS_DIR", documents)
        monkeypatch.setattr(f"{module}.IMAGES_DIR", images)
    return documents, images


@pytest.fixture(scope="session", autouse=True)
def cleanup_generated_reports():
    """Remove every report PDF created during the test session, keeping pre-existing files."""
    # Imported lazily: importing app.tools first at conftest load triggers a circular import.
    from app.tools.pdf_generator import REPORTS_DIR

    reports_dir = Path(REPORTS_DIR).resolve()
    existing = set(reports_dir.glob("*.pdf")) if reports_dir.exists() else set()

    yield

    if not reports_dir.exists():
        return
    for pdf in reports_dir.glob("*.pdf"):
        if pdf not in existing:
            pdf.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def offline_gemini(monkeypatch):
    """Run every test without a Gemini key so no test reaches the real network.

    Without a key the services use their offline paths (deterministic mock embeddings, fallback agent
    engine). Tests that need a "configured" client build it explicitly (see tests/test_embedding.py).
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
