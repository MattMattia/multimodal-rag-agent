import type { en } from "./en";

/** UI languages. Spanish is the default; English is picked from storage or `navigator.language`. */
export type Locale = "es" | "en";

export const LOCALES: readonly Locale[] = ["es", "en"];
export const DEFAULT_LOCALE: Locale = "es";
/** localStorage key that persists the visitor's language choice. */
export const LOCALE_STORAGE_KEY = "rag_locale";

/**
 * Shape of every UI dictionary, derived from the English one. `es.ts` is annotated with this type, so the
 * compiler rejects a missing or extra key in either language.
 */
export type Dictionary = typeof en;

export function isLocale(value: unknown): value is Locale {
  return value === "es" || value === "en";
}

/** BCP 47 tag used for `Intl` number and date formatting. */
export function intlTag(locale: Locale): string {
  return locale === "es" ? "es-ES" : "en-US";
}
