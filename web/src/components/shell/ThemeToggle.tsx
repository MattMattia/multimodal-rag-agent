"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";
const STORAGE_KEY = "rag-theme";
const NEXT: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };
const LABEL: Record<Theme, string> = { system: "🖥️ System", light: "☀️ Light", dark: "🌙 Dark" };

function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as Theme | null;
      if (saved && saved in NEXT) {
        setTheme(saved);
        applyTheme(saved);
      }
    } catch {
      // storage unavailable (private mode): keep the system theme
    }
  }, []);

  const cycle = () => {
    const next = NEXT[theme];
    setTheme(next);
    applyTheme(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
  };

  return (
    <button type="button" className="btn btn-ghost btn-sm" onClick={cycle} aria-label={`Theme: ${theme}. Switch theme`}>
      {LABEL[theme]}
    </button>
  );
}
