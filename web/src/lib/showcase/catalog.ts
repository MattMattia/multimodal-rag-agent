/** Contract-shaped views of the embedded corpus: document list/detail, demo status and seed results. */
import type {
  BffDemoStatus,
  DemoSeedResponse,
  DocumentDetailResponse,
  DocumentResponse,
} from "../contracts";
import { CORPUS_TIMESTAMP, type GoldenDocument, GOLDEN_DOCUMENTS, corpusTotals, findDocument } from "./corpus";

export const SHOWCASE_MODELS = {
  agent: "showcase-extractive-synthesizer",
  vision: "precomputed-golden-descriptions",
  embedding: "lexical-feature-hashing-512 (not semantic)",
} as const;

function toDocumentResponse(doc: GoldenDocument): DocumentResponse {
  return {
    id: doc.id,
    filename: doc.filename,
    file_type: "application/pdf",
    file_path: `uploads/documents/${doc.filename}`,
    upload_date: CORPUS_TIMESTAMP,
    status: "completed",
    error_message: null,
    doc_metadata: {
      demo_corpus: true,
      total_pages: doc.total_pages,
      total_tables: doc.total_tables,
      total_images: 1,
      total_chunks: doc.chunks.length,
    },
    total_chunks: doc.chunks.length,
    total_images: 1,
  };
}

export function listDocuments(): DocumentResponse[] {
  return GOLDEN_DOCUMENTS.map(toDocumentResponse);
}

export function documentDetail(id: string): DocumentDetailResponse | null {
  const doc = findDocument(id);
  if (!doc) return null;
  return {
    ...toDocumentResponse(doc),
    chunks: doc.chunks.map((c) => ({
      id: c.id,
      document_id: doc.id,
      parent_id: c.parent_id,
      content: c.content,
      chunk_type: c.chunk_type,
      page_number: c.page_number,
      chunk_metadata: c.chunk_metadata,
      created_at: CORPUS_TIMESTAMP,
    })),
    images: [
      {
        id: doc.image.id,
        document_id: doc.id,
        image_path: `uploads/images/${doc.image.filename}`,
        description: doc.image.description,
        page_number: doc.image.page_number,
        image_metadata: { image_index: 1, demo_corpus: true, caption: doc.image.caption },
        created_at: CORPUS_TIMESTAMP,
      },
    ],
  };
}

export function findImage(documentId: string, imageId: string): GoldenDocument["image"] | null {
  const doc = findDocument(documentId);
  return doc && doc.image.id === imageId ? doc.image : null;
}

export function showcaseStatus(): BffDemoStatus {
  const totals = corpusTotals();
  return {
    source: "showcase",
    db_dialect: "in-memory",
    demo_seeded: true,
    total_documents: totals.documents,
    total_chunks: totals.chunks,
    total_images: totals.images,
    gemini_configured: false,
    langfuse_enabled: false,
    active_models: { ...SHOWCASE_MODELS },
    embedding_mode: "mock",
  };
}

/** The embedded corpus is always present, so "restoring" it is an idempotent no-op. */
export function showcaseSeed(durationMs: number): DemoSeedResponse {
  return {
    documents_created: 0,
    documents_skipped: GOLDEN_DOCUMENTS.length,
    files_created: 0,
    chunks_created: 0,
    images_created: 0,
    duration_ms: Number(durationMs.toFixed(3)),
    demo_seeded: true,
  };
}
