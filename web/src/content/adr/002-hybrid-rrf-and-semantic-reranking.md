# ADR 002 — Hybrid RRF and semantic reranking

> Placeholder rendered by the web app. Phase 5 writes the canonical ADR in `docs/adr/002-hybrid-rrf-and-semantic-reranking.md`; keep this file in sync with it.

## Status

Accepted

## Context

Dense vectors capture paraphrases but miss exact identifiers (`m=16`, `$45M`, `A10`); BM25 is the opposite.

## Decision

- Run dense (pgvector HNSW, cosine) and sparse (PostgreSQL full-text / BM25) retrieval with a candidate window of `min(top_k * 4, 80)`.
- Fuse with **Reciprocal Rank Fusion**: `RRF(d) = sum 1 / (k + rank_i)` with `k = 60`, which needs no score calibration.
- Rerank the top `top_k * 3` blocks with a Gemini semantic reranker.
- Expose per-stage latency (`SearchDiagnostics`) in every search and agent event.

## Consequences

- Robust recall across lexical and semantic queries, measured by the 8-query benchmark.
- The reranker dominates latency (P95 about 310 ms), so it can be disabled per request.
