/**
 * In-memory mirror of `HybridSearchService.search` (app/services/rag_search.py):
 * dense (hashing stand-in, leaf chunks) + sparse (BM25, all chunks) → RRF k=60 → dedupe by parent block
 * → rerank window (top_k * 3) → parent-context expansion, with the same `SearchDiagnostics` stages.
 */
import type { SearchDiagnostics, SearchRequest, SearchResponse, SearchResultItem } from "../contracts";
import { type CorpusChunk, allChunks, chunkById, findDocument, leafChunks } from "./corpus";
import { cosine, hashEmbedding, isZeroVector } from "./dense";
import { ShowcaseError } from "./errors";
import { bm25Scores, tokenize } from "./lexical";

export const RRF_K = 60;
export const SEARCH_CANDIDATE_MULTIPLIER = 4;
export const MAX_RETRIEVAL_CANDIDATES = 80;
export const SHOWCASE_DB_DIALECT = "in-memory";

interface Candidate {
  chunk: CorpusChunk;
  score: number;
  rerank_score: number | null;
}

type Clock = () => number;
const defaultClock: Clock = () => performance.now();
const round = (value: number, digits: number): number => Number(value.toFixed(digits));

const LEAF_VECTORS = new Map<string, Float64Array>();
const TOKENS = new Map<string, string[]>();

function leafVector(chunk: CorpusChunk): Float64Array {
  let vector = LEAF_VECTORS.get(chunk.id);
  if (!vector) {
    vector = hashEmbedding(chunk.content);
    LEAF_VECTORS.set(chunk.id, vector);
  }
  return vector;
}

function chunkTokens(chunk: CorpusChunk): string[] {
  let tokens = TOKENS.get(chunk.id);
  if (!tokens) {
    tokens = tokenize(chunk.content);
    TOKENS.set(chunk.id, tokens);
  }
  return tokens;
}

/** RRF(d) = Σ 1 / (k + rank_i). Dense payload wins on collisions; ties keep insertion order (stable sort). */
export function rrfFuse<T extends { chunk_id: string }>(
  dense: readonly T[],
  sparse: readonly T[],
  k: number = RRF_K,
): Array<T & { score: number }> {
  const scores = new Map<string, number>();
  const items = new Map<string, T>();
  for (const ranking of [dense, sparse]) {
    ranking.forEach((item, index) => {
      if (!items.has(item.chunk_id)) items.set(item.chunk_id, item);
      scores.set(item.chunk_id, (scores.get(item.chunk_id) ?? 0) + 1 / (k + index + 1));
    });
  }
  return [...scores.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([id, score]) => ({ ...(items.get(id) as T), score }));
}

function denseRetrieval(queryVector: Float64Array, leaves: readonly CorpusChunk[], limit: number): Candidate[] {
  if (isZeroVector(queryVector)) return [];
  return leaves
    .map((chunk) => ({ chunk, score: cosine(queryVector, leafVector(chunk)), rerank_score: null }))
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

function sparseRetrieval(query: string, pool: readonly CorpusChunk[], limit: number): Candidate[] {
  const queryTokens = tokenize(query);
  if (queryTokens.length === 0) return [];
  const scores = bm25Scores(queryTokens, pool.map(chunkTokens));
  return pool
    .map((chunk, i) => ({ chunk, score: scores[i] ?? 0, rerank_score: null }))
    .filter((c) => c.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

function dedupeByParentBlock(items: readonly Candidate[]): Candidate[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const block = item.chunk.parent_id ?? item.chunk.id;
    if (seen.has(block)) return false;
    seen.add(block);
    return true;
  });
}

/**
 * Rerank STAND-IN (the live backend calls a Gemini cross-encoder): query-term coverage of the chunk plus
 * its parent block (60%) blended with hashed-vector cosine (40%), giving a 0..1 relevance score.
 */
function rerank(query: string, candidates: readonly Candidate[], topN: number): Candidate[] {
  if (candidates.length === 1) {
    const only = candidates[0]!;
    return [{ ...only, rerank_score: round(only.score, 4) }];
  }
  const queryTokens = [...new Set(tokenize(query))];
  const queryVector = hashEmbedding(query);
  return candidates
    .map((candidate) => {
      const parent = candidate.chunk.parent_id ? chunkById(candidate.chunk.parent_id) : undefined;
      const text = `${candidate.chunk.content}\n${parent?.content ?? ""}`;
      const tokens = new Set(tokenize(text));
      const coverage = queryTokens.length ? queryTokens.filter((t) => tokens.has(t)).length / queryTokens.length : 0;
      const similarity = cosine(queryVector, hashEmbedding(text));
      return { ...candidate, rerank_score: 0.6 * coverage + 0.4 * similarity };
    })
    .sort((a, b) => (b.rerank_score ?? 0) - (a.rerank_score ?? 0))
    .slice(0, topN);
}

function toResultItem(candidate: Candidate, rank: number, includeParent: boolean): SearchResultItem {
  const { chunk } = candidate;
  const parent = includeParent && chunk.parent_id ? chunkById(chunk.parent_id) : undefined;
  return {
    chunk_id: chunk.id,
    document_id: chunk.document_id,
    document_name: chunk.document_name,
    content: chunk.content,
    parent_id: chunk.parent_id,
    parent_content: parent?.content ?? null,
    chunk_type: chunk.chunk_type,
    page_number: chunk.page_number,
    score: round(candidate.score, 6),
    rerank_score: candidate.rerank_score === null ? null : round(candidate.rerank_score, 4),
    rank,
    metadata: chunk.chunk_metadata,
  };
}

export function assertSearchableDocument(filter: string | null): void {
  if (filter && !findDocument(filter)) {
    throw new ShowcaseError(
      404,
      `The document with filter_document_id '${filter}' does not exist. Omit the field to search every document.`,
    );
  }
}

export function searchCorpus(request: SearchRequest, clock: Clock = defaultClock): SearchResponse {
  const query = request.query.trim();
  const topK = request.top_k ?? 5;
  const mode = request.mode ?? "hybrid";
  const useRerank = request.rerank ?? true;
  const includeParent = request.include_parent ?? true;
  const filter = request.filter_document_id ?? null;

  assertSearchableDocument(filter);

  const totalStarted = clock();
  let embeddingMs = 0;
  let denseMs = 0;
  let sparseMs = 0;
  let rerankMs = 0;
  const limit = Math.min(topK * SEARCH_CANDIDATE_MULTIPLIER, MAX_RETRIEVAL_CANDIDATES);
  const pool = filter ? allChunks().filter((c) => c.document_id === filter) : allChunks();
  const leaves = new Set(leafChunks().map((c) => c.id));

  let dense: Candidate[] = [];
  let sparse: Candidate[] = [];
  if (mode === "hybrid" || mode === "dense") {
    let started = clock();
    const queryVector = hashEmbedding(query);
    embeddingMs = clock() - started;
    started = clock();
    dense = denseRetrieval(
      queryVector,
      pool.filter((c) => leaves.has(c.id)),
      limit,
    );
    denseMs = clock() - started;
  }
  if (mode === "hybrid" || mode === "sparse") {
    const started = clock();
    sparse = sparseRetrieval(query, pool, limit);
    sparseMs = clock() - started;
  }

  let started = clock();
  let fused: Candidate[];
  if (mode === "dense") fused = dense;
  else if (mode === "sparse") fused = sparse;
  else {
    const byId = new Map([...sparse, ...dense].map((c) => [c.chunk.id, c]));
    fused = rrfFuse(
      dense.map((c) => ({ chunk_id: c.chunk.id })),
      sparse.map((c) => ({ chunk_id: c.chunk.id })),
    ).map((f) => ({ ...(byId.get(f.chunk_id) as Candidate), score: f.score }));
  }
  const rawCandidates = fused.length;
  fused = dedupeByParentBlock(fused);
  const rrfMs = clock() - started;
  const dedupedBlocks = fused.length;

  let ranked: Candidate[];
  if (useRerank && fused.length) {
    started = clock();
    ranked = rerank(query, fused.slice(0, topK * 3), topK);
    rerankMs = clock() - started;
  } else {
    ranked = fused.slice(0, topK);
  }

  const results = ranked.map((c, i) => toResultItem(c, i + 1, includeParent));
  const diagnostics: SearchDiagnostics = {
    db_dialect: SHOWCASE_DB_DIALECT,
    embedding_ms: round(embeddingMs, 3),
    dense_ms: round(denseMs, 3),
    sparse_ms: round(sparseMs, 3),
    rrf_fusion_ms: round(rrfMs, 3),
    rerank_ms: round(rerankMs, 3),
    total_ms: round(clock() - totalStarted, 3),
    raw_candidates_count: rawCandidates,
    deduped_blocks_count: dedupedBlocks,
  };
  return { query, mode, total_results: results.length, results, diagnostics };
}
