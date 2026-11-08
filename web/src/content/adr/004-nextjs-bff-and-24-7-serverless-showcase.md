# ADR 004 — Next.js BFF with a serverless showcase fallback

## Status

Accepted (implemented in `web/src/app/api/*`, `web/src/lib/server/backend.ts` and `web/src/lib/showcase/*`).

## Context

A reviewer should be able to open the project at any time, even when the API machine is off. Exposing the
FastAPI backend directly to a browser has two problems. The browser would need the backend's API key or CORS
rules for every origin, and any outage of the backend would show as a broken page.

The web app is Next.js 15.5.29 with React 19.2.9. Its routes run on the server, so the backend URL and the
API key never reach the browser bundle.

## Decision

The Next.js app is a backend-for-frontend (BFF). Its route handlers under `web/src/app/api/*` call FastAPI
first and fall back to an embedded showcase engine only when the backend is unreachable.

### Configuration (server side only)

| Variable | Default | Use |
|----------|---------|-----|
| `FASTAPI_URL` | unset | Base URL of the backend. Unset means the showcase serves every route. |
| `API_KEY` | unset | Sent as `X-API-Key` to the backend. It is read on the server only and is never a `NEXT_PUBLIC_*` variable. |
| `FASTAPI_TIMEOUT_MS` | `3000` | Time to wait for response headers. Chat streaming uses 15 s and uploads use 30 s. |

### When the fallback runs

`callBackend` in `web/src/lib/server/backend.ts` classifies the outcome:

| Outcome | Result |
|---------|--------|
| `FASTAPI_URL` is unset | Fallback (`unreachable`) |
| Network error or timeout while waiting for headers | Fallback (`unreachable`) |
| HTTP 502 or 504 | Fallback (`unreachable`) |
| Any other HTTP status, including 2xx, 4xx, 500 and 503 | Passed through to the browser unchanged |
| Client closed the request | No fallback; the upstream request is cancelled |

The rule that a live 503 is passed through is deliberate: a live backend may return it on purpose. Only "no backend behind the proxy" triggers the showcase.

Every response carries `x-rag-source` (`fastapi` or `showcase`), so a client can tell which engine answered. Each fallback writes a server-side warning that names the path and the reason, never the URL or the key.

### Showcase engine

The showcase is a set of dependency-free TypeScript modules in `web/src/lib/showcase/`:

| Module | Role |
|--------|------|
| `corpus.ts` and `golden-corpus.json` | The Golden Corpus, generated from the backend with the same splitters and ids as the seeder (ADR 001). |
| `dense.ts` | Dense stand-in: FNV-1a feature hashing of stemmed tokens and character trigrams into 512 dimensions, L2-normalized. It is not a language model. |
| `lexical.ts` | TypeScript port of `app/services/lexical.py`, with BM25 (`k1 = 1.5`, `b = 0.75`). |
| `search.ts` | Same stages as the backend: dense and sparse legs, RRF with `k = 60`, candidate window `min(top_k × 4, 80)`, deduplication by parent block, rerank window `top_k × 3`. |
| `agent.ts` | Deterministic, extractive ReAct-shaped turn. It runs the search as a tool call and streams an answer built from the retrieved text. |
| `evaluation.ts` | Mirror of `RAGEvaluationService` over the embedded corpus. |
| `reports.ts` and `pdf.ts` | Stateless PDF generation for reports. |

Uploads are not available in the showcase. The `POST /api/documents` fallback answers with an explanation that uploads need the live backend and that the showcase serves the read-only Golden Corpus.

### Routes using the fallback

Routes that call `liveOrShowcase`: `search`, `documents` (list, detail, image, upload), `reports/[filename]`, `sessions` (list, detail, history, export), `feedback`, `demo/seed`, `demo/evaluate`. The chat stream (`chat/stream`) calls `callBackend` directly and falls back to `showcaseStream`.

## Consequences

Positive:

- The public showcase works without a running backend, and it still exercises the search pipeline shape (dense, sparse, RRF, rerank, parent expansion).
- Secrets stay on the server. The browser calls only `/api/*` on the same origin.
- One response shape for both engines: the showcase returns the same JSON types that FastAPI returns, defined in `web/src/lib/contracts.ts`. The `x-rag-source` header tells them apart.

Trade-offs and limitations:

- **The showcase is not the real retrieval.** Its dense leg is a hashing stand-in and its rerank is a lexical stand-in. Its sparse leg is BM25, which matches the SQLite backend, not the PostgreSQL full-text leg. The evaluation response carries `SHOWCASE_EVALUATION_WARNING` in `warnings`, and the benchmark view renders that list.
- **The agent is not a language model.** `agent.ts` answers with extracted evidence from the corpus, so streamed text does not come from Gemini.
- **The corpus is a snapshot.** Changing the Golden Corpus requires regenerating `golden-corpus.json` from the backend.
- **A fallback can hide an outage.** Users see a working page while the backend is down. The `x-rag-source` header and the server log are the only signals.
- **Timeouts are short by default.** A sleeping backend host that answers slower than 3 s is treated as unavailable, even if it would have answered later.
- **Upload and feedback writes are not stored by the showcase.** Those actions require the live backend.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| Browser calls FastAPI directly | Exposes CORS and key handling to the browser and gives no offline view. |
| Static export of the Golden Corpus only | Cannot show the ReAct turn, the search diagnostics or the benchmark logic. The showcase engine keeps those in code. |
| Run FastAPI in a serverless function | Would move the database, Gemini calls and reranker into a serverless runtime. The project keeps FastAPI as the full-stack backend and uses the showcase only as a read-only fallback. |
| Stop at Streamlit | Streamlit needs a running Python process; it is kept for the full enterprise mode. |

## Next step

Return to ADR 003 for the three modes, or see the README section on execution modes.
