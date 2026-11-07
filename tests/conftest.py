"""Shared pytest fixtures for the whole test suite."""

from pathlib import Path

import pytest


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
