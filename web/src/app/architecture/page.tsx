import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import type { Metadata } from "next";
import { AdrViewer, type AdrDocument } from "@/components/architecture/AdrViewer";
import { ServiceStatus } from "@/components/architecture/ServiceStatus";
import { TriModalMap } from "@/components/architecture/TriModalMap";

export const metadata: Metadata = { title: "Architecture & ADRs" };
export const dynamic = "force-static";

/**
 * ADRs are read at build time from `src/content/adr/*.md`. They mirror `docs/adr/` (written in Phase 5);
 * keep both folders in sync.
 */
async function loadAdrs(): Promise<AdrDocument[]> {
  const dir = path.join(process.cwd(), "src", "content", "adr");
  const files = (await readdir(dir)).filter((f) => f.endsWith(".md")).sort();
  return Promise.all(
    files.map(async (file) => {
      const content = await readFile(path.join(dir, file), "utf8");
      const title = /^#\s+(.+)$/m.exec(content)?.[1] ?? file;
      return { slug: file.replace(/\.md$/, ""), title, content };
    }),
  );
}

export default async function ArchitecturePage() {
  const adrs = await loadAdrs();
  return (
    <div className="stack" style={{ gap: "var(--space-4)" }}>
      <header className="page-header">
        <h1>🏗️ System Architecture, Telemetry & ADRs</h1>
        <p>Three execution modes, one contract: Vercel serverless showcase, zero-Docker SQLite and the full PostgreSQL + pgvector stack.</p>
      </header>
      <div className="arch-grid">
        <TriModalMap />
        <ServiceStatus />
      </div>
      <AdrViewer adrs={adrs} />
    </div>
  );
}
