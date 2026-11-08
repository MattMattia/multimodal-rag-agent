# ADR 003 — Tri-modal zero-dependency architecture

> Placeholder rendered by the web app. Phase 5 writes the canonical ADR in `docs/adr/003-tri-modal-zero-dependency-architecture.md`; keep this file in sync with it.

## Status

Accepted

## Context

Evaluators must be able to try the project at any time, whatever they have installed and even when the author's machine is off.

## Decision

1. **Cloud showcase** — the Next.js app on Vercel answers from an embedded Golden Corpus when FastAPI is unreachable.
2. **Zero-Docker local** — `python run.py` falls back to SQLite (`aiosqlite`) with exact Python vector search and BM25, and auto-seeds the corpus.
3. **Full enterprise** — Docker Compose with PostgreSQL 16 + pgvector (HNSW m=16, ef_construction=64), Langfuse, Streamlit and Next.js.

## Consequences

- One codebase, three execution modes, the same contracts.
- Dialect-aware code paths must be tested in both PostgreSQL and SQLite.
