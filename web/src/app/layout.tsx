import type { Metadata, Viewport } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { NavTabs } from "@/components/shell/NavTabs";
import { StatusBadge } from "@/components/shell/StatusBadge";
import { StatusProvider } from "@/components/shell/StatusProvider";
import { ThemeToggle } from "@/components/shell/ThemeToggle";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Multimodal RAG Agent Studio", template: "%s · Multimodal RAG Agent" },
  description:
    "Hybrid RRF retrieval, an autonomous ReAct agent and a scientific RAG benchmark — live on FastAPI + pgvector or 24/7 on Vercel.",
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
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <StatusProvider>
          <header className="topbar">
            <Link href="/" className="brand" aria-label="Multimodal RAG Agent home">
              <span className="brand-mark" aria-hidden="true">
                RAG
              </span>
              <span>
                Multimodal RAG Agent
                <small>Hybrid RRF · ReAct · Gemini Vision</small>
              </span>
            </Link>
            <NavTabs />
            <div className="topbar-end">
              <StatusBadge />
              <ThemeToggle />
            </div>
          </header>
          <main id="main" className="main" tabIndex={-1}>
            {children}
          </main>
        </StatusProvider>
      </body>
    </html>
  );
}
