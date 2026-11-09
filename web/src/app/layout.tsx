import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { LanguageToggle } from "@/components/shell/LanguageToggle";
import { NavTabs } from "@/components/shell/NavTabs";
import { BrandLink, SkipLink } from "@/components/shell/ShellChrome";
import { StatusBadge } from "@/components/shell/StatusBadge";
import { StatusProvider } from "@/components/shell/StatusProvider";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import { DEFAULT_LOCALE } from "@/lib/i18n/types";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Multimodal RAG Agent Studio", template: "%s · Multimodal RAG Agent" },
  description:
    "RAG multimodal con recuperación híbrida RRF, agente ReAct autónomo y benchmark científico · Hybrid RRF retrieval, an autonomous ReAct agent and a scientific RAG benchmark — live on FastAPI + pgvector or 24/7 on Vercel.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f7fb" },
    { media: "(prefers-color-scheme: dark)", color: "#0b0e17" },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // The server renders the default locale; LocaleProvider applies the stored/browser language after mount
  // and keeps <html lang> in sync.
  return (
    <html lang={DEFAULT_LOCALE}>
      <body>
        <LocaleProvider>
          <SkipLink />
          <StatusProvider>
            <header className="topbar">
              <BrandLink />
              <NavTabs />
              <div className="topbar-end">
                <StatusBadge />
                <LanguageToggle />
                <ThemeToggle />
              </div>
            </header>
            <main id="main" className="main" tabIndex={-1}>
              {children}
            </main>
          </StatusProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
