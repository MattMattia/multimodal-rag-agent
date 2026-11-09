"use client";

import { useId, useState } from "react";
import type { CitationItem, DocumentImageResponse, SearchResultItem } from "@/lib/contracts";
import { api } from "@/lib/client/api";
import { formatNumber } from "@/lib/i18n/format";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import { Markdown } from "../Markdown";

/** Multimodal citation with RRF / Rerank badges and an inline table or image viewer. */
export function CitationCard({ citation, evidence }: { citation: CitationItem; evidence?: SearchResultItem }) {
  const { locale, t } = useLocale();
  const typeLabels: Record<string, string> = t.agent.citation.types;
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
    <article className="citation" aria-label={t.agent.citation.source(citation.document_name)}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="badge">{typeLabels[citation.chunk_type] ?? citation.chunk_type}</span>
        {citation.page_number != null && <span className="subtle">{t.agent.citation.page(citation.page_number)}</span>}
      </div>
      <span className="citation-title">{citation.document_name}</span>
      <div className="row">
        {evidence && (
          <span className="badge badge-info" title={t.agent.citation.rrfTitle}>
            RRF {formatNumber(locale, evidence.score, 4)}
          </span>
        )}
        {rerank !== null && (
          <span className="badge badge-accent" title={t.agent.citation.rerankTitle}>
            Rerank {formatNumber(locale, rerank, 2)}
          </span>
        )}
        {evidence && <span className="badge">#{evidence.rank}</span>}
      </div>
      {evidence && <p className="citation-snippet">{evidence.content}</p>}
      {viewable && (
        <button type="button" className="btn btn-sm" aria-expanded={open} aria-controls={viewerId} onClick={() => void toggle()}>
          {open
            ? t.agent.citation.hide
            : citation.chunk_type === "table"
              ? t.agent.citation.viewTable
              : citation.chunk_type === "image_description"
                ? t.agent.citation.viewImage
                : t.agent.citation.viewContext}
        </button>
      )}
      {open && (
        <div className="viewer" id={viewerId}>
          {citation.chunk_type === "image_description" && evidence && (
            <>
              {image === "loading" && <p className="subtle">{t.agent.citation.loadingImage}</p>}
              {image === "missing" && <p className="subtle">{t.agent.citation.imageMissing}</p>}
              {image && typeof image === "object" && (
                // eslint-disable-next-line @next/next/no-img-element -- served by the BFF with auth on the server
                <img src={`/api/documents/${image.document_id}/images/${image.id}`} alt={image.description} loading="lazy" />
              )}
            </>
          )}
          {evidence ? (
            <Markdown source={evidence.chunk_type === "table" ? evidence.content : (evidence.parent_content ?? evidence.content)} />
          ) : (
            <p className="subtle">{t.agent.citation.noEvidence}</p>
          )}
        </div>
      )}
    </article>
  );
}
