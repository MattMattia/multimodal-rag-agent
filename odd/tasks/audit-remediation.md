# Audit remediation (5 phases)

Objective: fix every finding of `CLAUDE_AUDIT_MASTER_PROMPT.md`. Branch: `fix/audit-remediation`. Delivery: `ask-on-risk`, one work-unit commit per phase. Test runner: `.venv/Scripts/python -m pytest` (local venv, Python 3.11; Docker daemon not running at start).

## Specs

Each spec is the finding with the same ID in `CLAUDE_AUDIT_MASTER_PROMPT.md` section 3. That file is the verbatim source: its "Ubicación exacta", "Causa Raíz" and "Solución Exacta" are the acceptance criteria. Line numbers there are from commit `1294c90` and are hints; verify against current code.

- S1 BUG-01 (lines 64-75): each agent tool runs exactly once per call (5 sites in `app/services/agent.py`).
- S2 BUG-02 (77-80): `RerankerService.rerank()` body fully inside one telemetry span, dead code removed.
- S3 BUG-03 (82-87): `frontend/app.py` imports `json` and `html`; SSE parse catches `json.JSONDecodeError` only.
- S4 BUG-04 (89-92): `TelemetryService` propagates the active parent through a `ContextVar` when `parent=None`.
- S5 BUG-05 (94-101): streaming keeps newlines/Markdown, no artificial sleep, `record_generation` per ReAct turn.
- S6 BUG-06 (103-106): `rerank_score` passed to every `CitationItem` (both sites + `_deduplicate_citations`).
- S7 SEC-01 (112-116): `validate_webhook_url` blocks SSRF (schemes, allow-list, private/loopback/link-local/multicast/reserved IPs, internal names).
- S8 SEC-02 (118-128): upload sanitizes filename, path containment, `or` instead of `and`, magic bytes, `MAX_UPLOAD_SIZE_MB = 25` with HTTP 413 and partial-file removal.
- S9 SEC-03 (130-133): ReportLab text escaped with `xml.sax.saxutils.escape` before `<br/>` replacement.
- S10 SEC-04 (135-146): optional `X-API-Key` (`secrets.compare_digest`, open when unset), delete removes extracted PNGs, 500 errors hide `str(e)` when `not DEBUG`, safe CORS default origins.
- S11 SEC-05 (148-151): non-root `appuser` in both Dockerfiles, no `--reload` in base `CMD`, API `HEALTHCHECK`.
- S12 PERF-01 (157-164): report PDF and pdfplumber work run via `asyncio.to_thread`.
- S13 PERF-02 (166-171): `Image.open` closed with `with`, `_working_model` cached, `google.generativeai` fallback removed.
- S14 PERF-03 (173-180): English GIN index, HNSW `WITH (m = 16, ef_construction = 64)`, `websearch_to_tsquery`.
- S15 PERF-04 (182-189): parent-child dedup in `HybridSearchService.search`; no `db.flush()` in loops, one flush before embeddings, one commit at the end.
- S16 PERF-05 (191-198): pool `pool_size=10, max_overflow=20, pool_recycle=1800`, clean `get_db()`, last 20 messages sent to Gemini.
- S17 DX-01 (204-213): `total_chunks`, `@st.cache_data(ttl=300, show_spinner=False)` on `fetch_file_bytes`, `html.escape` on `doc_name`/`chunk_type`.
- S18 DX-02 (215-227): `tests/conftest.py` report cleanup fixture, `@pytest.mark.asyncio` in `test_reranker.py`, no real network in tests, new tests listed there.
- S19 DX-03 (229-241): drop unused deps, dedupe imports, `datetime.now(timezone.utc)`, clean `.gitignore`/`.env.example`, README tree, `pyproject.toml` for ruff/mypy.
- S20 Phase 5 (282-292): syntax check, full suite green, residual test files cleaned, executive summary.

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 Phase 1 P0 bugs | S1-S6, S17 | delegated `tdd-guide` (user asked for ECC subagents; context backstop) | pending | |
| T2 Phase 2 security | S7-S11 | delegated `tdd-guide` writer + `security-reviewer` verifier (Risk item 2) | pending | |
| T3 Phase 3 async/DB/RAG | S12-S16 | delegated writer + `database-reviewer` and `code-reviewer` (Python) | pending | |
| T4 Phase 4 tests/deps/docs | S18-S19 | delegated writer (refactor-cleaner/doc-updater role) | pending | |
| T5 Phase 5 verification | S20 | inline `verification-loop` | pending | |

## Log

- L1 (2026-11-07, user): "Lee @CLAUDE_AUDIT_MASTER_PROMPT.md y ejecuta el plan completo de 5 fases utilizando los subagentes y flujos de ECC (/plan, /tdd, security-reviewer, python-reviewer, database-reviewer, refactor-cleaner y /verify o /verify-ecc)."
- L2: Spot-checked BUG-01 (duplicate `_dispatch_tool_call` at agent.py:485), BUG-02 (reranker early span close) and BUG-03 (no `import json`): confirmed. Agent types `python-reviewer`, `refactor-cleaner`, `doc-updater`, `planner` are not installed; substitutes: `code-reviewer`, `general-purpose`.
