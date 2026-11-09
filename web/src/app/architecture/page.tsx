import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import type { Metadata } from "next";
import { AdrViewer, type AdrDocument, type AdrVersion } from "@/components/architecture/AdrViewer";
import { ArchitectureHeader } from "@/components/architecture/ArchitectureHeader";
import { ServiceStatus } from "@/components/architecture/ServiceStatus";
import { TriModalMap } from "@/components/architecture/TriModalMap";

export const metadata: Metadata = { title: "Arquitectura y ADRs · Architecture & ADRs" };
export const dynamic = "force-static";

const SPANISH_SUFFIX = ".es.md";

async function readVersion(file: string, fallbackTitle: string): Promise<AdrVersion> {
  const content = await readFile(file, "utf8");
  return { title: /^#\s+(.+)$/m.exec(content)?.[1] ?? fallbackTitle, content };
}

/**
 * ADRs are read at build time from `src/content/adr/`: `X.md` (English) and its Spanish translation `X.es.md`.
 * They mirror `docs/adr/`; keep both folders in sync. A missing `.es.md` falls back to the English text.
 */
async function loadAdrs(): Promise<AdrDocument[]> {
  const dir = path.join(process.cwd(), "src", "content", "adr");
  const files = await readdir(dir);
  const available = new Set(files);
  const bases = files.filter((f) => f.endsWith(".md") && !f.endsWith(SPANISH_SUFFIX)).sort();
  return Promise.all(
    bases.map(async (file) => {
      const slug = file.replace(/\.md$/, "");
      const english = await readVersion(path.join(dir, file), file);
      const spanishFile = `${slug}${SPANISH_SUFFIX}`;
      const spanish = available.has(spanishFile) ? await readVersion(path.join(dir, spanishFile), file) : english;
      return { slug, en: english, es: spanish };
    }),
  );
}

export default async function ArchitecturePage() {
  const adrs = await loadAdrs();
  return (
    <div className="stack" style={{ gap: "var(--space-4)" }}>
      <ArchitectureHeader />
      <div className="arch-grid">
        <TriModalMap />
        <ServiceStatus />
      </div>
      <AdrViewer adrs={adrs} />
    </div>
  );
}
