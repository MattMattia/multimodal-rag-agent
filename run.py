"""Universal launcher.

    python run.py                  start the API (PostgreSQL if reachable, otherwise SQLite Zero-Docker)
    python run.py --export-openapi write docs/openapi.json and exit
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OPENAPI_PATH = ROOT / "docs" / "openapi.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the Multimodal RAG & Agent API.")
    parser.add_argument("--export-openapi", action="store_true", help="write docs/openapi.json and exit")
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="bind port (default: 8000)")
    return parser.parse_args(argv)


def export_openapi(target: Path | None = None) -> Path:
    """Write the full OpenAPI 3.1 schema (UTF-8, independent of the console code page)."""
    from app.main import app

    target = target or OPENAPI_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(app.openapi(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return target


def _banner(host: str, port: int) -> str:
    from app.core.database import get_active_db_dialect

    base = f"http://{'localhost' if host in ('0.0.0.0', '127.0.0.1') else host}:{port}"  # noqa: S104
    mode = "PostgreSQL + pgvector" if get_active_db_dialect() == "postgresql" else "SQLite Zero-Docker"
    return "\n".join(
        [
            "",
            f"  Ready  (database: {mode}, Golden Corpus auto-seeded)",
            f"  API        {base}",
            f"  Swagger    {base}/docs",
            f"  OpenAPI    {base}/openapi.json",
            "  Streamlit  streamlit run frontend/app.py   (http://localhost:8501)",
            "  Web        cd web && npm run dev            (http://localhost:3001)",
            "",
        ]
    )


async def _serve(host: str, port: int) -> None:
    import uvicorn

    server = uvicorn.Server(uvicorn.Config("app.main:app", host=host, port=port, log_level="info"))
    task = asyncio.create_task(server.serve())
    while not server.started and not task.done():
        await asyncio.sleep(0.1)
    if server.started:
        print(_banner(host, port), flush=True)
    await task


def serve(host: str, port: int) -> None:
    """Start uvicorn; the app lifespan runs `init_db` (dialect detection, SQLite fallback, auto-seed)."""
    asyncio.run(_serve(host, port))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.export_openapi:
        written = export_openapi()
        print(f"OpenAPI schema written to {written}")
        return 0
    serve(args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
