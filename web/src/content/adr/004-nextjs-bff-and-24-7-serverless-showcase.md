# ADR 004 — Next.js BFF and 24/7 serverless showcase

> Placeholder rendered by the web app. Phase 5 writes the canonical ADR in `docs/adr/004-nextjs-bff-and-24-7-serverless-showcase.md`; keep this file in sync with it.

## Status

Accepted

## Context

The browser must never hold the backend key, and a recruiter opening the Vercel link must get a working product even when the backend is down.

## Decision

- Route Handlers under `/api/*` act as a **Backend-for-Frontend**: the backend URL and key are read on the server only and sent as `X-API-Key`.
- Each handler calls FastAPI first with a short timeout. On a network failure, timeout or gateway error it answers from `showcase-engine.ts`; a live 4xx is passed through unchanged.
- The showcase engine embeds the Golden Corpus, ranks with a lexical hashing dense stand-in plus BM25 fused by RRF k=60, streams real SSE events, builds valid PDFs and runs the benchmark with an explicit not-semantic disclosure.
- Types come from the FastAPI OpenAPI document (`openapi-typescript`).

## Consequences

- 24/7 availability at zero hosting cost for the showcase.
- The showcase is honest but not semantic; the UI labels which engine answered.
