"use client";

import Link from "next/link";
import { useLocale } from "@/lib/i18n/LocaleProvider";

/** Localized skip link and brand of the top bar (the root layout itself is a server component). */
export function SkipLink() {
  const { t } = useLocale();
  return (
    <a className="skip-link" href="#main">
      {t.shell.skipToContent}
    </a>
  );
}

export function BrandLink() {
  const { t } = useLocale();
  return (
    <Link href="/" className="brand" aria-label={t.shell.brandHome}>
      <span className="brand-mark" aria-hidden="true">
        RAG
      </span>
      <span>
        Multimodal RAG Agent
        <small>Hybrid RRF · ReAct · Gemini Vision</small>
      </span>
    </Link>
  );
}
