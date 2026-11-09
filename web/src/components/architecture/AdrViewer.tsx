"use client";

import { type KeyboardEvent, useId, useState } from "react";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import type { Locale } from "@/lib/i18n/types";
import { Markdown } from "../Markdown";

export interface AdrVersion {
  title: string;
  content: string;
}

/** One ADR in both languages; the loader fills `es` with the English version when no `.es.md` exists. */
export type AdrDocument = { slug: string } & Record<Locale, AdrVersion>;

/** Tabbed viewer for the engineering ADRs (WAI-ARIA tabs with arrow-key navigation), in the active language. */
export function AdrViewer({ adrs }: { adrs: readonly AdrDocument[] }) {
  const { locale, t } = useLocale();
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
    <section className="card" aria-label={t.architecture.adr.label}>
      <h2>{t.architecture.adr.title}</h2>
      <div className="tabs" role="tablist" aria-label={t.architecture.adr.tabs} onKeyDown={onKeyDown}>
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
            {adr.slug.slice(0, 3)} · {adr[locale].title.replace(/^ADR \d+ [—-] /, "")}
          </button>
        ))}
      </div>
      <div id={`${baseId}-panel`} role="tabpanel" aria-labelledby={`${baseId}-tab-${index}`} tabIndex={0} lang={locale}>
        <Markdown source={current[locale].content} />
      </div>
    </section>
  );
}
