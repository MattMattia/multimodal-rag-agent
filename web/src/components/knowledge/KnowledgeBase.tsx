"use client";

import { type DragEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DocumentChunkResponse, DocumentDetailResponse, DocumentResponse } from "@/lib/contracts";
import { api } from "@/lib/client/api";
import { useDemoStatus } from "../shell/StatusProvider";
import { Markdown } from "../Markdown";

const ACCEPTED = ".pdf,.png,.jpg,.jpeg,.webp";
const STATUS_BADGE: Record<string, string> = {
  completed: "badge-success",
  processing: "badge-warning",
  pending: "badge-warning",
  failed: "badge-danger",
};

interface TreeNode {
  chunk: DocumentChunkResponse;
  children: DocumentChunkResponse[];
}

export function buildTree(chunks: readonly DocumentChunkResponse[]): TreeNode[] {
  const children = new Map<string, DocumentChunkResponse[]>();
  for (const chunk of chunks) {
    if (chunk.parent_id) children.set(chunk.parent_id, [...(children.get(chunk.parent_id) ?? []), chunk]);
  }
  return chunks
    .filter((c) => !c.parent_id)
    .sort((a, b) => (a.page_number ?? 0) - (b.page_number ?? 0))
    .map((chunk) => ({ chunk, children: children.get(chunk.id) ?? [] }));
}

export function KnowledgeBase() {
  const { status, refresh } = useDemoStatus();
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [selected, setSelected] = useState<DocumentDetailResponse | null>(null);
  const [details, setDetails] = useState<DocumentDetailResponse[]>([]);
  const [dragging, setDragging] = useState(false);
  const [message, setMessage] = useState<{ kind: "info" | "danger"; text: string } | null>(null);
  const [working, setWorking] = useState<"upload" | "seed" | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const docs = await api.documents();
      setDocuments(docs);
      const loaded = await Promise.allSettled(docs.slice(0, 12).map((d) => api.document(d.id)));
      const ok = loaded.flatMap((r) => (r.status === "fulfilled" ? [r.value] : []));
      setDetails(ok);
      setSelected((current) => ok.find((d) => d.id === current?.id) ?? ok[0] ?? null);
    } catch (error) {
      setMessage({ kind: "danger", text: error instanceof Error ? error.message : "Could not load documents." });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, status?.source]);

  const upload = async (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    setWorking("upload");
    try {
      const result = await api.upload(file);
      setMessage({ kind: "info", text: `${result.filename}: ${result.message} (status ${result.status}).` });
      await load();
    } catch (error) {
      setMessage({ kind: "danger", text: error instanceof Error ? error.message : "Upload failed." });
    } finally {
      setWorking(null);
    }
  };

  const seed = async () => {
    setWorking("seed");
    try {
      const result = await api.seed();
      setMessage({
        kind: "info",
        text: `Golden Corpus ready: ${result.documents_created} created, ${result.documents_skipped} already present, ${result.chunks_created} chunks, ${result.duration_ms.toFixed(0)} ms.`,
      });
      await Promise.all([load(), refresh()]);
    } catch (error) {
      setMessage({ kind: "danger", text: error instanceof Error ? error.message : "Seeding failed." });
    } finally {
      setWorking(null);
    }
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    void upload(event.dataTransfer.files);
  };

  const tree = useMemo(() => (selected ? buildTree(selected.chunks ?? []) : []), [selected]);
  const images = details.flatMap((d) => (d.images ?? []).map((img) => ({ ...img, document: d.filename })));

  return (
    <div className="stack" style={{ gap: "var(--space-4)" }}>
      <header className="page-header">
        <h1>📚 Multimodal Knowledge Base & Vision Inspector</h1>
        <p>Hierarchical parent-child chunking, Markdown tables and diagrams described by Gemini Vision — the exact units the retriever ranks.</p>
      </header>
      {message && (
        <div className={`alert alert-${message.kind}`} role={message.kind === "danger" ? "alert" : "status"}>
          {message.text}
        </div>
      )}
      <div className="kb-grid">
        <div className="stack">
          <section className="card stack">
            <h2>⬆️ Upload</h2>
            <div
              className="dropzone"
              data-active={dragging}
              role="button"
              tabIndex={0}
              aria-label="Upload a PDF or image: drop a file here or press Enter to browse"
              onClick={() => input.current?.click()}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  input.current?.click();
                }
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <span style={{ fontSize: "1.6rem" }} aria-hidden="true">
                📥
              </span>
              <strong>{working === "upload" ? "Uploading…" : "Drag & drop a PDF or image"}</strong>
              <span className="subtle">PDF, PNG, JPG or WEBP · validated by magic bytes on the backend</span>
            </div>
            <input ref={input} type="file" accept={ACCEPTED} hidden onChange={(e) => void upload(e.target.files)} />
            {status?.source === "showcase" && (
              <p className="subtle" style={{ margin: 0 }}>
                Uploads need the live backend; the showcase serves the read-only Golden Corpus.
              </p>
            )}
            <button type="button" className="btn btn-primary" onClick={() => void seed()} disabled={working !== null}>
              {working === "seed" ? <span className="spinner" aria-hidden="true" /> : "🚀"} Restore Golden Demo Corpus
            </button>
          </section>
          <section className="card stack">
            <h2>🗃️ Documents ({documents.length})</h2>
            <ul className="doc-list">
              {documents.map((doc) => (
                <li key={doc.id}>
                  <button
                    type="button"
                    aria-pressed={selected?.id === doc.id}
                    onClick={() => void api.document(doc.id).then(setSelected, () => setSelected(null))}
                  >
                    <strong style={{ display: "block", overflowWrap: "anywhere" }}>{doc.filename}</strong>
                    <span className="row" style={{ marginTop: "var(--space-1)" }}>
                      <span className={`badge ${STATUS_BADGE[doc.status] ?? ""}`}>{doc.status}</span>
                      <span className="badge">{doc.total_chunks} chunks</span>
                      <span className="badge">{doc.total_images} images</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <div className="stack">
          <section className="card stack" aria-label="Parent-child explorer">
            <h2>🌳 Parent-child explorer {selected && <span className="subtle">— {selected.filename}</span>}</h2>
            {!selected ? (
              <p className="subtle">Select a document.</p>
            ) : (
              <ul className="tree">
                {tree.map(({ chunk, children }) => (
                  <li key={chunk.id}>
                    <details>
                      <summary>
                        <span className="badge badge-accent">{chunk.chunk_type}</span>
                        <span className="badge">p. {chunk.page_number ?? "–"}</span>
                        <span className="badge">{children.length ? `${children.length} children` : "leaf"}</span>
                        <span className="subtle" style={{ overflowWrap: "anywhere" }}>
                          {chunk.content.replace(/[#|*]/g, "").slice(0, 90)}…
                        </span>
                      </summary>
                      <div style={{ padding: "0 var(--space-3) var(--space-3)" }}>
                        {chunk.chunk_type === "table" ? <Markdown source={chunk.content} /> : <p className="chunk-text">{chunk.content}</p>}
                      </div>
                      {children.length > 0 && (
                        <ol className="children" aria-label="Child chunks (embedded leaves)">
                          {children.map((child) => (
                            <li key={child.id}>
                              <span className="badge">child {String(child.chunk_metadata?.child_index ?? "")}</span>
                              <p className="chunk-text">{child.content}</p>
                            </li>
                          ))}
                        </ol>
                      )}
                    </details>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card stack" aria-label="Vision gallery">
            <h2>👁️ Vision gallery — diagrams analysed by Gemini Vision</h2>
            {images.length === 0 ? (
              <p className="subtle">No extracted images yet.</p>
            ) : (
              <div className="gallery">
                {images.map((img) => (
                  <figure key={img.id} className="card card-subtle">
                    {/* eslint-disable-next-line @next/next/no-img-element -- dynamic BFF route, not a static asset */}
                    <img src={`/api/documents/${img.document_id}/images/${img.id}`} alt={img.description} loading="lazy" />
                    <figcaption>
                      <strong>{img.document}</strong> · p. {img.page_number ?? "–"}
                      <br />
                      {img.description}
                    </figcaption>
                  </figure>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
