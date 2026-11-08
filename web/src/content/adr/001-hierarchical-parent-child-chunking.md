# ADR 001 — Hierarchical parent-child chunking

> Placeholder rendered by the web app. Phase 5 writes the canonical ADR in `docs/adr/001-hierarchical-parent-child-chunking.md`; keep this file in sync with it.

## Status

Accepted

## Context

Long pages mix several topics. Embedding whole pages dilutes the vector; embedding tiny fragments loses the context the LLM needs to answer.

## Decision

- Split text into **parent blocks** (1200 characters, 120 overlap) and **child chunks** (350 characters, 40 overlap).
- Only **leaf chunks** get embeddings; parents with children are context only, so they never compete with their own children in the top-k.
- Tables become Markdown parent chunks and diagrams become Gemini Vision description chunks.
- Retrieval deduplicates by parent block and expands each hit to its parent content.

## Consequences

- Precise matching on small chunks with full-paragraph context in the prompt.
- More rows per document; the dedupe step keeps the result list diverse.
