# Web — Next.js 15 BFF + 24/7 Showcase Engine

Next.js 15 (App Router, React 19, strict TypeScript) frontend for the Multimodal RAG & Autonomous Agent platform.
Four views: **Agent Studio**, **Knowledge Base**, **Benchmark Lab** and **Architecture & ADRs**.

## How it works

- The browser only calls the Route Handlers under `/api/*` (Backend-for-Frontend).
- Each handler calls `FASTAPI_URL` first, with a short timeout. Both `FASTAPI_URL` and `API_KEY` are read on the server only.
- If FastAPI is unreachable (network error, timeout or a 502/503/504 gateway error), the handler answers from
  `src/lib/showcase-engine.ts`. This engine holds the embedded Golden Corpus, runs hybrid RRF retrieval (k=60), streams SSE events,
  builds PDF reports and runs the benchmark. Any other live response, 4xx included, is passed through unchanged.
- The top bar shows which engine answered: `🟢 Live FastAPI + pgvector Cluster` or `⚡ Vercel Serverless 24/7 Showcase Engine`.
- In the showcase, the "dense" retriever is a **lexical feature-hashing stand-in, not a semantic model**.
  Its reranker and answers are extractive too, with no LLM. The benchmark reports this with `embedding_mode: "mock"` and a warning.

## Languages (es / en)

- The UI is bilingual. The **🇪🇸 ES / 🇺🇸 EN** button next to the status badge and the theme toggle switches every view instantly.
- Default: Spanish, unless `navigator.language` starts with `en`. The choice is stored in `localStorage` under `rag_locale` and kept in `<html lang>`.
- Strings live in `src/lib/i18n/en.ts` and `es.ts`; `es.ts` is typed with the `Dictionary` shape of `en.ts`, and a test checks key parity.
- The active language travels with each request: chat body `language` (`es` | `en` | `auto`), `?lang=es|en` on session export and `/api/demo/evaluate`.
  The showcase engine answers, builds PDFs and writes benchmark warnings in that language; Spanish report links end in `.es.pdf`.

## Run

```bash
cp .env.example .env.local   # set FASTAPI_URL (and API_KEY if the backend requires it)
npm install
npm run dev                  # http://localhost:3001
```

| Script | Purpose |
| --- | --- |
| `npm run dev` / `build` / `start` | Next.js on port 3001 |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint (next/core-web-vitals + typescript) |
| `npm test` | Vitest: engine, BFF fallback, components |
| `npm run contracts:generate` | Regenerate `src/lib/api-schema.ts` from `src/lib/openapi.json` |
| `npm run check:bundle` | After a build, fail if server-only env names appear in `.next/static` |

Scripts call `node node_modules/...` directly. The repository path contains `&`, which breaks npm's Windows `.cmd` shims.

## Deploy to Vercel

1. Import the repository and set **Root Directory** to `web`. The framework preset is Next.js.
2. Optionally add the environment variables `FASTAPI_URL`, `API_KEY` and `FASTAPI_TIMEOUT_MS`. Never use a `NEXT_PUBLIC_` prefix for them.
3. Deploy. Without `FASTAPI_URL`, every request is served by the showcase engine.

## Contract

`src/lib/openapi.json` comes from FastAPI's `app.openapi()` and `src/lib/api-schema.ts` is generated from it.
`src/lib/contracts.ts` names those types and adds the SSE event union, which OpenAPI cannot describe.
`src/lib/showcase/golden-corpus.json` is generated from `app/services/demo_corpus.py` using the backend's own chunk splitters.

SSE events: `tool_start {tool_name, tool_input}` → `tool_end {duration_ms, diagnostics}` → `token` → `metadata {…, message_id}`.
Feedback uses `metadata.message_id`. If an older backend omits it, the UI reads the id from the session history instead.

Known contract gaps in the backend:

- `CitationItem` has no RRF score or content, so the UI re-runs `/api/search` once per turn to fill the citation cards.
- Report `download_url` uses `/uploads/reports/...`. The UI rewrites it to `/api/reports/...`.

The ADR viewer renders `src/content/adr/*.md` (English) and `*.es.md` (Spanish, same base name; a missing translation falls back to English). Keep these files in sync with `docs/adr/`.
