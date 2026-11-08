# ADR 002 — Hybrid retrieval with RRF and semantic reranking

## Status

Accepted (implemented in `HybridSearchService` and `RerankerService`).

## Context

Dense vectors miss exact tokens such as serial numbers, acronyms, tax identifiers and table labels. Lexical
search misses paraphrases and cross-language questions. Each signal fails on different queries, and the two
score scales are not comparable: cosine similarity and a full-text rank cannot be added directly.

Once the candidates are fused, a fused score still measures only rank agreement. A chunk that repeats the
query words can rank high without answering the question.

## Decision

The search runs in four stages.

1. **Candidate retrieval per leg.** Each leg returns at most `retrieval_limit = min(top_k × SEARCH_CANDIDATE_MULTIPLIER, 80)` rows. With the defaults (`SEARCH_CANDIDATE_MULTIPLIER = 4`, `top_k = 5`), that is 20 rows per leg.
2. **Reciprocal Rank Fusion.** `score(d) = Σ 1 / (RRF_K + rank_i(d))` over the two lists, with `rank` starting at 1 and `RRF_K = 60`. No weights are tuned. A chunk found by both legs collects both contributions.
3. **Deduplication by parent block.** Candidates are reduced to one per `parent_id or chunk_id` (see ADR 001).
4. **Semantic reranking.** The first `top_k × 3` blocks go to `RerankerService`, which asks Gemini (`GEMINI_AGENT_MODEL`, default `gemini-1.5-pro`) to score each snippet from 0.0 to 1.0. Snippets are cut to `RERANK_MAX_SNIPPET_CHARS = 800`. The call is limited to `RERANK_TIMEOUT_SECONDS = 8.0`. The best `top_k` are returned with `rerank_score`.

Leg details by database dialect:

| Leg | PostgreSQL | SQLite (zero-Docker) |
|-----|------------|----------------------|
| Dense | `embedding IS NOT NULL`, pgvector `cosine_distance` over `vector(768)`, similarity = `1 − distance` clipped to [0, 1] | Exact cosine computed in Python over every leaf with an embedding |
| Sparse | Full-text: `websearch_to_tsquery` in `spanish` and `english`, matched with OR; rank = `GREATEST(ts_rank_cd(es), ts_rank_cd(en))` | BM25 (`k1 = 1.5`, `b = 0.75`) computed in Python over all chunks |
| Index | HNSW (`vector_cosine_ops`, `m = 16`, `ef_construction = 64`); GIN on `to_tsvector('spanish', content)` and `to_tsvector('english', content)` | None (no ANN, no FTS index) |

The `mode` parameter selects `dense`, `sparse` or `hybrid`. Only `hybrid` runs RRF. `rerank=false` skips stage 4.

The reranker falls back to the RRF order, without a model call, in these cases: no usable Gemini client, a timeout, or any exception. The fallback keeps the RRF order and sets `rerank_score` to the RRF score.

## Consequences

Positive:

- No score calibration. RRF depends only on ranks, so the two legs need no shared scale.
- Exact-term matches survive: the lexical leg recovers identifiers that embeddings blur.
- Reranking can rescue a candidate that is lexically strong but off-topic, and it is bounded by a timeout.
- Diagnostics expose each stage (`embedding_ms`, `dense_ms`, `sparse_ms`, `rrf_fusion_ms`, `rerank_ms`, candidate counts), so the trade-offs are measurable.

Trade-offs and limitations:

- **Two model-dependent steps.** Each query may call the embedding API and the reranker. Latency and quota depend on Gemini.
- **The deterministic fallback is not a relevance score.** When the reranker falls back, `rerank_score` repeats the RRF score. It orders results but does not measure relevance.
- **The sparse leg indexes parent blocks too.** Parents have no vectors but do have text, so a parent can match lexically and then be merged with its children by deduplication.
- **Candidate windows are small by design.** With `top_k = 5` the dense leg sees at most 20 rows, so a relevant chunk that ranks below 20 in both legs is never reranked.
- **Offline benchmarks are not semantic.** Without `GOOGLE_API_KEY`, dense and hybrid use mock vectors. The evaluation reports `embedding_mode: "mock"`, a warning, and `semantic: false` for those modes. Only the `sparse` numbers are meaningful offline.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| Weighted linear fusion of normalized scores | Needs score normalization and tuned weights, which the project cannot calibrate without labeled data. |
| Dense only | Misses exact identifiers and table labels, which the Golden Corpus tests. |
| Lexical only | Misses paraphrases and cross-lingual queries; the evaluation includes both. |
| Local cross-encoder reranker | Adds model weights and a second runtime. The project already uses Gemini and must stay installable without Docker. |
| External search engine (Elasticsearch, OpenSearch) | Adds a service that the zero-Docker mode cannot provide. |

## Next step

Read ADR 003 (`docs/adr/003-tri-modal-zero-dependency-architecture.md`) for how the same pipeline runs on SQLite without pgvector.
