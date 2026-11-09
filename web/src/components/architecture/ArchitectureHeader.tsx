"use client";

import { useLocale } from "@/lib/i18n/LocaleProvider";

/** Localized page header of the Architecture view (the page itself is a static server component). */
export function ArchitectureHeader() {
  const { t } = useLocale();
  return (
    <header className="page-header">
      <h1>{t.architecture.title}</h1>
      <p>{t.architecture.intro}</p>
    </header>
  );
}
