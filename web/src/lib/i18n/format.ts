import { intlTag, type Locale } from "./types";

/** Fixed-decimal number in the locale's notation (e.g. 0.0328 in English, 0,0328 in Spanish). */
export function formatNumber(locale: Locale, value: number, digits: number): string {
  return new Intl.NumberFormat(intlTag(locale), {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    useGrouping: false,
  }).format(value);
}

/** Milliseconds with the precision the UI has always used: 0 decimals from 100 ms, else 1 (or 2 under 10 ms). */
export function formatMs(locale: Locale, ms: number, fine = false): string {
  const digits = ms >= 100 ? 0 : fine && ms < 10 ? 2 : 1;
  return formatNumber(locale, ms, digits);
}

export function formatDate(locale: Locale, iso: string): string {
  return new Date(iso).toLocaleDateString(intlTag(locale));
}
