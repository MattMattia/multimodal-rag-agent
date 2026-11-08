# ADR 001 — Hierarchical parent-child chunking

## Status

Accepted (implemented in the ingestion pipeline and in the Golden Corpus seeder).

## Context

Long pages mix several topics. Embedding a whole page dilutes the vector, so a query about one paragraph
scores low against it. Embedding very small fragments keeps precision but removes the surrounding context
that the LLM needs to answer. A single chunk size cannot serve both needs.

The ingestion pipeline (`app/services/ingestion.py`) receives PDF text, table Markdown and Gemini Vision
descriptions of diagrams. All of them go through the same splitter pair.

## Decision

Each text is split into two levels with `RecursiveCharacterTextSplitter` (separators `\n\n`, `\n`, `. `, ` `, empty string):

| Level | Size / overlap | Settings | Stored as | Embedded |
|-------|----------------|----------|-----------|----------|
| Parent block | 1200 / 120 characters | `PARENT_CHUNK_SIZE` / `PARENT_CHUNK_OVERLAP` | `DocumentChunk` with `parent_id = NULL` and `chunk_metadata.level = "parent"` | No, when it has children |
| Child chunk | 350 / 40 characters | `CHILD_CHUNK_SIZE` / `CHILD_CHUNK_OVERLAP` | `DocumentChunk` with `parent_id` pointing at its parent | Yes |

Rules that the code enforces:

- **Only leaf chunks get embeddings.** A parent that has children keeps `embedding = NULL`. Leaves are the chunks that no other row references through `parent_id` (`_embed_leaf_chunks` in the seeder and the equivalent block in `IngestionService`). A parent is never a competitor of its own children in the top-k.
- **Children are created only when the parent splits.** `_add_hierarchical_chunks` creates children only when the child splitter returns more than one piece. A parent that fits in one child-sized piece therefore has no children, is itself a leaf, and is embedded.
- **Tables are standalone parent-level chunks** (`chunk_type = "table"`, `parent_id = NULL`). They have no children, so they are leaves and get embeddings.
- **Vision descriptions** of diagrams and receipts are chunked with the same pair (`chunk_type = "image_description"`). A description that starts with the vision error prefix is kept as a note on `DocumentImage` and is not indexed.
- **Retrieval deduplicates by parent block and expands to the parent.** Each candidate belongs to the block `parent_id or chunk_id`. Only the best-ranked candidate of each block is kept (`_dedupe_by_parent_block`). `attach_parent_context` then loads the parent text into `parent_content`, which is the context sent to the reranker and to the agent.

## Consequences

Positive:

- Vectors describe focused passages (350 characters), while the answer context is the 1200-character block.
- Table and diagram content is searchable without special retrieval code.
- A parent cannot push its own children out of the top-k, because parents carry no vector.

Trade-offs and limitations:

- **Two overlap windows cost storage and time.** Parent rows are stored as text, and the child splitter runs on every parent.
- **Existing data is not migrated.** Rows embedded before the leaf-only rule (R2-BUG-04) may still carry vectors for parents. They must be re-embedded, and the project log records that the existing PostgreSQL embeddings were produced by an older model or by mock vectors.
- **The sizes are fixed defaults.** They are tuned for the Golden Corpus and for the 768-dimension `gemini-embedding-001` model. Changing them does not reindex existing documents.
- **Mock embeddings carry no meaning.** Without `GOOGLE_API_KEY`, the leaves receive deterministic SHA-256 vectors. The hierarchy then works mechanically, but dense similarity does not measure semantics.

## Alternatives considered

| Alternative | Why not chosen |
|-------------|----------------|
| Embed whole pages | Diluted vectors; poor precision on long, mixed-topic pages. |
| One flat chunk size (for example 350 or 1200) | Forces a choice between precision and context. |
| Embed every chunk, parents included | Parents compete with their children and inflate the candidate pool with duplicate context. |
| Sentence-window retrieval or late chunking | More complex to implement and to reason about in SQL. The parent-child model needs only a `parent_id` column. |

## Next step

Read ADR 002 (`docs/adr/002-hybrid-rrf-and-semantic-reranking.md`) for how leaves are retrieved and fused.
