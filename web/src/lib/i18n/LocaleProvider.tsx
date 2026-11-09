"use client";

import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { en } from "./en";
import { es } from "./es";
import { DEFAULT_LOCALE, type Dictionary, isLocale, type Locale, LOCALE_STORAGE_KEY } from "./types";

const DICTIONARIES: Record<Locale, Dictionary> = { es, en };

export interface LocaleState {
  locale: Locale;
  setLocale: (next: Locale) => void;
  toggleLocale: () => void;
  t: Dictionary;
}

const LocaleContext = createContext<LocaleState>({
  locale: DEFAULT_LOCALE,
  setLocale: () => {},
  toggleLocale: () => {},
  t: DICTIONARIES[DEFAULT_LOCALE],
});

/** Stored choice first, then the browser language ("en*" → English), otherwise Spanish. */
function preferredLocale(): Locale {
  try {
    const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
    if (isLocale(stored)) return stored;
  } catch {
    // storage unavailable (private mode): fall back to the browser language
  }
  return typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("en") ? "en" : DEFAULT_LOCALE;
}

/**
 * Shares the active UI language. The server and the first client render use the default locale (no hydration
 * mismatch); the stored or browser preference is applied right after mount, like ThemeToggle does for themes.
 */
export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    setLocaleState(preferredLocale());
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, next);
    } catch {
      // ignore: the choice still applies to this tab
    }
  }, []);

  const toggleLocale = useCallback(() => setLocale(locale === "es" ? "en" : "es"), [locale, setLocale]);

  const value = useMemo<LocaleState>(
    () => ({ locale, setLocale, toggleLocale, t: DICTIONARIES[locale] }),
    [locale, setLocale, toggleLocale],
  );
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleState {
  return useContext(LocaleContext);
}
