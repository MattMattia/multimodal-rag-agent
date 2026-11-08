"use client";

import { type KeyboardEvent, useId, useState } from "react";
import { Markdown } from "../Markdown";

export interface AdrDocument {
  slug: string;
  title: string;
  content: string;
}

/** Tabbed viewer for the engineering ADRs (WAI-ARIA tabs with arrow-key navigation). */
export function AdrViewer({ adrs }: { adrs: readonly AdrDocument[] }) {
  const [index, setIndex] = useState(0);
  const baseId = useId();
  const current = adrs[index];

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const next = (index + (event.key === "ArrowRight" ? 1 : adrs.length - 1)) % adrs.length;
    setIndex(next);
    document.getElementById(`${baseId}-tab-${next}`)?.focus();
  };

  if (!current) return null;
  return (
    <section className="card" aria-label="Architecture Decision Records">
      <h2>📐 Architecture Decision Records</h2>
      <div className="tabs" role="tablist" aria-label="ADRs" onKeyDown={onKeyDown}>
        {adrs.map((adr, i) => (
          <button
            key={adr.slug}
            id={`${baseId}-tab-${i}`}
            type="button"
            role="tab"
            className="tab"
            aria-selected={i === index}
            aria-controls={`${baseId}-panel`}
            tabIndex={i === index ? 0 : -1}
            onClick={() => setIndex(i)}
          >
            {adr.slug.slice(0, 3)} · {adr.title.replace(/^ADR \d+ — /, "")}
          </button>
        ))}
      </div>
      <div id={`${baseId}-panel`} role="tabpanel" aria-labelledby={`${baseId}-tab-${index}`} tabIndex={0}>
        <Markdown source={current.content} />
      </div>
    </section>
  );
}
