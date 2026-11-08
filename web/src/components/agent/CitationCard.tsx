"use client";

import { useId, useState } from "react";
import type { CitationItem, DocumentImageResponse, SearchResultItem } from "@/lib/contracts";
import { api } from "@/lib/client/api";
import { Markdown } from "../Markdown";

const TYPE_LABEL: Record<string, string> = { text: "📝 Text", table: "📊 Table", image_description: "🖼️ Diagram" };

/** Multimodal citation with RRF / Rerank badges and an inline table or image viewer. */
export function CitationCard({ citation, evidence }: { citation: CitationItem; evidence?: SearchResultItem }) {
  const [open, setOpen] = useState(false);
  const [image, setImage] = useState<DocumentImageResponse | null | "loading" | "missing">(null);
  const viewerId = useId();
  const rerank = citation.rerank_score ?? evidence?.rerank_score ?? null;
  const viewable = citation.chunk_type === "table" || citation.chunk_type === "image_description" || Boolean(evidence);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && citation.chunk_type === "image_description" && evidence && image === null) {
      setImage("loading");
      try {
        const detail = await api.document(evidence.document_id);
        const images = detail.images ?? [];
        const match = images.find((img) => img.page_number === citation.page_number) ?? images[0];
        setImage(match ?? "missing");
      } catch {
        setImage("missing");
      }
    }
  };

  return (
    <article className="citation" aria-label={`Source ${citation.document_name}`}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="badge">{TYPE_LABEL[citation.chunk_type] ?? citation.chunk_type}</span>
        {citation.page_number != null && <span className="subtle">p. {citation.page_number}</span>}
      </div>
      <span className="citation-title">{citation.document_name}</span>
      <div className="row">
        {evidence && (
          <span className="badge badge-info" title="Reciprocal Rank Fusion score (k=60)">
            RRF {evidence.score.toFixed(4)}
          </span>
        )}
        {rerank !== null && (
          <span className="badge badge-accent" title="Semantic reranker relevance (0-1)">
            Rerank {rerank.toFixed(2)}
          </span>
        )}
        {evidence && <span className="badge">#{evidence.rank}</span>}
      </div>
      {evidence && <p className="citation-snippet">{evidence.content}</p>}
      {viewable && (
        <button type="button" className="btn btn-sm" aria-expanded={open} aria-controls={viewerId} onClick={() => void toggle()}>
          {open ? "Hide" : citation.chunk_type === "table" ? "View table" : citation.chunk_type === "image_description" ? "View image" : "View context"}
        </button>
      )}
      {open && (
        <div className="viewer" id={viewerId}>
          {citation.chunk_type === "image_description" && evidence && (
            <>
              {image === "loading" && <p className="subtle">Loading image…</p>}
              {image === "missing" && <p className="subtle">Image file not available.</p>}
              {image && typeof image === "object" && (
                // eslint-disable-next-line @next/next/no-img-element -- served by the BFF with auth on the server
                <img src={`/api/documents/${image.document_id}/images/${image.id}`} alt={image.description} loading="lazy" />
              )}
            </>
          )}
          {evidence ? (
            <Markdown source={evidence.chunk_type === "table" ? evidence.content : (evidence.parent_content ?? evidence.content)} />
          ) : (
            <p className="subtle">Evidence details are not available for this citation.</p>
          )}
        </div>
      )}
    </article>
  );
}
