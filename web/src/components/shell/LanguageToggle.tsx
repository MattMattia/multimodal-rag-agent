"use client";

import { useLocale } from "@/lib/i18n/LocaleProvider";

/** Switches the UI between Spanish and English; the choice is persisted in localStorage (`rag_locale`). */
export function LanguageToggle() {
  const { t, toggleLocale } = useLocale();
  return (
    <button type="button" className="btn btn-ghost btn-sm" onClick={toggleLocale} aria-label={t.shell.language.toggleLabel}>
      {t.shell.language.badge}
    </button>
  );
}
