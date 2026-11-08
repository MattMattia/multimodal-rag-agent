/**
 * Golden Demo Corpus embedded in TypeScript.
 *
 * `golden-corpus.json` is generated from the backend (`app/services/demo_corpus.py` chunked by the same
 * `IngestionService` parent/child splitters that `demo_seeder.py` uses), so the 3 documents, their tables,
 * diagram descriptions and facts are identical to the seeded database. Document ids are the same
 * `uuid5(DEMO_NAMESPACE, filename)` values the seeder writes; chunk and image ids are deterministic too.
 */
import data from "./golden-corpus.json";

export type ChunkType = "text" | "table" | "image_description";

export interface GoldenChunk {
  id: string;
  parent_id: string | null;
  content: string;
  chunk_type: ChunkType;
  page_number: number;
  chunk_metadata: Record<string, unknown>;
}

export interface GoldenImage {
  id: string;
  filename: string;
  kind: "architecture" | "bars" | "matrix";
  caption: string;
  description: string;
  page_number: number | null;
}

export interface GoldenDocument {
  id: string;
  filename: string;
  title: string;
  image: GoldenImage;
  total_pages: number;
  total_tables: number;
  chunks: GoldenChunk[];
}

export interface GoldenEvalQuery {
  id: string;
  category: string;
  query: string;
  expected_doc_filenames: string[];
  expected_keywords: string[];
}

/** A corpus chunk joined with its document, ready for retrieval. */
export interface CorpusChunk extends GoldenChunk {
  document_id: string;
  document_name: string;
}

export const GOLDEN_DOCUMENTS: readonly GoldenDocument[] = data.docs as GoldenDocument[];
export const GOLDEN_EVAL_QUERIES: readonly GoldenEvalQuery[] = data.queries;
/** Fixed timestamp for the embedded corpus (it is not uploaded at runtime). */
export const CORPUS_TIMESTAMP = "2026-01-01T00:00:00Z";

const ALL_CHUNKS: readonly CorpusChunk[] = GOLDEN_DOCUMENTS.flatMap((doc) =>
  doc.chunks.map((chunk) => ({ ...chunk, document_id: doc.id, document_name: doc.filename })),
);
const PARENT_IDS = new Set(ALL_CHUNKS.flatMap((c) => (c.parent_id ? [c.parent_id] : [])));
const CHUNK_BY_ID = new Map(ALL_CHUNKS.map((c) => [c.id, c]));

export function allChunks(): readonly CorpusChunk[] {
  return ALL_CHUNKS;
}

/** Leaf chunks are the only ones with embeddings (parents with children only provide context). */
export function leafChunks(): readonly CorpusChunk[] {
  return ALL_CHUNKS.filter((c) => !PARENT_IDS.has(c.id));
}

export function chunkById(id: string): CorpusChunk | undefined {
  return CHUNK_BY_ID.get(id);
}

export function findDocument(id: string): GoldenDocument | undefined {
  return GOLDEN_DOCUMENTS.find((d) => d.id === id);
}

export function corpusTotals(): { documents: number; chunks: number; images: number } {
  return { documents: GOLDEN_DOCUMENTS.length, chunks: ALL_CHUNKS.length, images: GOLDEN_DOCUMENTS.length };
}
