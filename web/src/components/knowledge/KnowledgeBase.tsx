"use client";

import { type DragEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DocumentChunkResponse, DocumentDetailResponse, DocumentResponse } from "@/lib/contracts";
import { api } from "@/lib/client/api";
import { formatNumber } from "@/lib/i18n/format";
import { useLocale } from "@/lib/i18n/LocaleProvider";
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
  const { locale, t } = useLocale();
  const k = t.knowledge;
  const statusLabels: Record<string, string> = k.status;
  // Read through a ref so a language switch does not refetch the documents.
  const loadError = useRef(k.errors.load);
  useEffect(() => {
    loadError.current = k.errors.load;
  }, [k.errors.load]);
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
      setMessage({ kind: "danger", text: error instanceof Error ? error.message : loadError.current });
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
      setMessage({ kind: "info", text: k.uploadResult(result.filename, result.message, result.status) });
      await load();
    } catch (error) {
      setMessage({ kind: "danger", text: error instanceof Error ? error.message : k.errors.upload });
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
        text: k.seedResult(result.documents_created, result.documents_skipped, result.chunks_created, formatNumber(locale, result.duration_ms, 0)),
      });
      await Promise.all([load(), refresh()]);
    } catch (error) {
      setMessage({ kind: "danger", text: error instanceof Error ? error.message : k.errors.seed });
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
        <h1>{k.title}</h1>
        <p>{k.intro}</p>
      </header>
      {message && (
        <div className={`alert alert-${message.kind}`} role={message.kind === "danger" ? "alert" : "status"}>
          {message.text}
        </div>
      )}
      <div className="kb-grid">
        <div className="stack">
          <section className="card stack">
            <h2>{k.uploadTitle}</h2>
            <div
              className="dropzone"
              data-active={dragging}
              role="button"
              tabIndex={0}
              aria-label={k.dropzoneLabel}
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
              <strong>{working === "upload" ? k.uploading : k.dropHint}</strong>
              <span className="subtle">{k.formats}</span>
            </div>
            <input ref={input} type="file" accept={ACCEPTED} hidden onChange={(e) => void upload(e.target.files)} />
            {status?.source === "showcase" && (
              <p className="subtle" style={{ margin: 0 }}>
                {k.showcaseUploads}
              </p>
            )}
            <button type="button" className="btn btn-primary" onClick={() => void seed()} disabled={working !== null}>
              {working === "seed" ? <span className="spinner" aria-hidden="true" /> : "🚀"} {k.restore}
            </button>
          </section>
          <section className="card stack">
            <h2>{k.documents(documents.length)}</h2>
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
                      <span className={`badge ${STATUS_BADGE[doc.status] ?? ""}`}>{statusLabels[doc.status] ?? doc.status}</span>
                      <span className="badge">{k.chunks(doc.total_chunks)}</span>
                      <span className="badge">{k.images(doc.total_images)}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <div className="stack">
          <section className="card stack" aria-label={k.explorerLabel}>
            <h2>{k.explorerTitle} {selected && <span className="subtle">— {selected.filename}</span>}</h2>
            {!selected ? (
              <p className="subtle">{k.selectDocument}</p>
            ) : (
              <ul className="tree">
                {tree.map(({ chunk, children }) => (
                  <li key={chunk.id}>
                    <details>
                      <summary>
                        <span className="badge badge-accent">{chunk.chunk_type}</span>
                        <span className="badge">{k.page(String(chunk.page_number ?? "–"))}</span>
                        <span className="badge">{children.length ? k.children(children.length) : k.leaf}</span>
                        <span className="subtle" style={{ overflowWrap: "anywhere" }}>
                          {chunk.content.replace(/[#|*]/g, "").slice(0, 90)}…
                        </span>
                      </summary>
                      <div style={{ padding: "0 var(--space-3) var(--space-3)" }}>
                        {chunk.chunk_type === "table" ? <Markdown source={chunk.content} /> : <p className="chunk-text">{chunk.content}</p>}
                      </div>
                      {children.length > 0 && (
                        <ol className="children" aria-label={k.childChunks}>
                          {children.map((child) => (
                            <li key={child.id}>
                              <span className="badge">{k.child(String(child.chunk_metadata?.child_index ?? ""))}</span>
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

          <section className="card stack" aria-label={k.galleryLabel}>
            <h2>{k.galleryTitle}</h2>
            {images.length === 0 ? (
              <p className="subtle">{k.noImages}</p>
            ) : (
              <div className="gallery">
                {images.map((img) => (
                  <figure key={img.id} className="card card-subtle">
                    {/* eslint-disable-next-line @next/next/no-img-element -- dynamic BFF route, not a static asset */}
                    <img src={`/api/documents/${img.document_id}/images/${img.id}`} alt={img.description} loading="lazy" />
                    <figcaption>
                      <strong>{img.document}</strong> · {k.page(String(img.page_number ?? "–"))}
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
