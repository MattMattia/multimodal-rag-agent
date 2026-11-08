# ADR 003 — Tri-modal execution with a zero-Docker SQLite fallback

## Status

Accepted (implemented in `app/core/database.py`, `app/services/rag_search.py`, `app/services/lexical.py`, `app/services/demo_seeder.py`).

## Context

The project must be runnable by a reviewer in minutes, on any machine, without knowing its infrastructure.
The full stack needs PostgreSQL with pgvector, Langfuse, Streamlit and the API. A reviewer who has only Python
should still see working retrieval, and a reviewer who has Docker should get the full stack. The cloud
showcase is a third entry point for when no machine is running at all.

Two constraints shape the choice. The same code must run on both databases, and the retrieval results on
SQLite must be correct, even though SQLite has no vector index.

## Decision

Three execution modes share one code base. The database dialect is chosen from `DATABASE_URL` and can fall back at startup.

| Mode | Entry point | Database | Retrieval | Who it is for |
|------|-------------|----------|-----------|---------------|
| 1. Cloud showcase | Next.js on Vercel, root directory `web` | None on the server; the BFF serves an embedded Golden Corpus | TypeScript showcase engine (see ADR 004) | Reviewers with a browser only |
| 2. Zero-Docker local | `python run.py` (SQLite) | `sqlite+aiosqlite:///./rag_standalone.db` | Exact cosine and BM25 in Python | Engineers with Python and no Docker |
| 3. Full enterprise | `docker compose up` | PostgreSQL 16 with pgvector | pgvector HNSW and GIN full-text | Production-like evaluation, Langfuse and Streamlit |

### Startup fallback

`init_db()` in `app/core/database.py` tries `create_schema` on the configured engine. If that fails and `AUTO_FALLBACK_SQLITE = true` (the default), the engine is rebound to `sqlite+aiosqlite:///./rag_standalone.db` and the schema is created again. The decision is made once, at startup. If SQLite is already configured, the fallback is skipped.

After the schema exists, `_auto_seed_if_empty` seeds the Golden Corpus when `AUTO_SEED_DEMO_CORPUS = true` and `documents` is empty.

### Dialect-specific code

- **Column types.** Models use `JSON().with_variant(JSONB, "postgresql")` and `embedding` is `vector(EMBEDDING_DIMENSION)` on PostgreSQL and a JSON array of floats on SQLite.
- **Indexes.** The HNSW and GIN indexes are created only on PostgreSQL. `create_schema` returns before them on SQLite.
- **Dense leg.** PostgreSQL uses pgvector `cosine_distance`. SQLite computes exact cosine in Python over the leaves that have an embedding.
- **Sparse leg.** PostgreSQL uses `websearch_to_tsquery` in Spanish and English. SQLite uses BM25 in Python (`app/services/lexical.py`), with accent folding, a light stemmer, and Spanish and English stopwords. The Python tokenizer is ported to TypeScript for the showcase, so both sides rank the same way.
- **Dialect detection.** `get_active_db_dialect()` returns `"sqlite"` or `"postgresql"`, and `HybridSearchService` reads the dialect of the session it receives.

### Golden Corpus

The seeder (`app/services/demo_seeder.py`) writes three generated PDF documents, each with a PNG image (files under `uploads/documents` and `uploads/images`, generated with ReportLab) and their chunks with the same splitters as ingestion (ADR 001). Without `GOOGLE_API_KEY`, the leaves receive deterministic mock vectors. With a key, the leaves are embedded through Gemini.

## Consequences

Positive:

- A reviewer can run retrieval, the Golden Corpus and the evaluation without Docker and without an API key.
- The same tests run on both databases (see the README test section, which uses `TEST_DATABASE_URL`).
- The full stack remains available with one command, with pgvector indexes and Langfuse traces.

Trade-offs and limitations:

- **SQLite retrieval is O(N).** Every query computes cosine over every leaf and BM25 over every chunk. That is acceptable for the Golden Corpus and for a single user, and it does not scale to large corpora.
- **"Zero-dependency" means zero services.** The Python requirements still include `pgvector`, `aiosqlite` and `reportlab`. What is removed is the need for Docker, PostgreSQL and a vector server.
- **The fallback is decided once, at startup.** The code selects the database only inside `init_db()`. If PostgreSQL fails later, the fallback is not triggered at runtime.
- **Offline results are not semantic.** Without a key, the dense leg uses SHA-256 mock vectors. The evaluation labels this (`embedding_mode: "mock"`).
- **Rate limiting is per process.** The sliding window lives in memory (`app/core/rate_limit.py`), keyed by socket IP. Several workers would each keep their own counters. The limiter is off under pytest.
- **Data written before the R2-BUG-04 fix is not corrected.** Existing PostgreSQL rows that carry embeddings for parents, or vectors from an older model, need re-embedding.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| Docker only | Excludes reviewers without Docker, which is the main evaluation barrier. |
| SQLite only | No pgvector, no HNSW, no GIN; the enterprise path would not be exercised. |
| A local vector store (FAISS, Chroma, LanceDB) as the zero-Docker backend | A second retrieval stack to keep consistent with PostgreSQL. The SQLite path keeps the same service layer and the same parent-child model, and changes only the dense and sparse legs. |
| Fully client-side demo only | Cannot show the real ingestion, the agent with real tools, or the Python services. Covered by mode 1 for the read-only view. |

## Next step

Read ADR 004 (`docs/adr/004-nextjs-bff-and-24-7-serverless-showcase.md`) for the cloud mode and its fallback rules.
