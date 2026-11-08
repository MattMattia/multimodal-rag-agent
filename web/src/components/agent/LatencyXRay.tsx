import type { SearchDiagnostics } from "@/lib/contracts";

export const XRAY_STAGES = [
  { key: "embedding_ms", label: "Query embedding", color: "var(--stage-embedding)" },
  { key: "dense_ms", label: "Dense retrieval", color: "var(--stage-dense)" },
  { key: "sparse_ms", label: "Sparse BM25", color: "var(--stage-sparse)" },
  { key: "rrf_fusion_ms", label: "RRF fusion + dedupe", color: "var(--stage-fusion)" },
  { key: "rerank_ms", label: "Semantic rerank", color: "var(--stage-rerank)" },
] as const;

const fmt = (ms: number): string => (ms >= 100 ? ms.toFixed(0) : ms.toFixed(ms >= 10 ? 1 : 2));

/** Latency X-ray of one RAG search (`SearchDiagnostics`): a stacked bar of every pipeline stage in ms. */
export function LatencyXRay({ diagnostics }: { diagnostics: SearchDiagnostics }) {
  const stagesTotal = XRAY_STAGES.reduce((sum, s) => sum + diagnostics[s.key], 0);
  const scale = stagesTotal > 0 ? stagesTotal : 1;
  const summary = XRAY_STAGES.map((s) => `${s.label} ${fmt(diagnostics[s.key])} ms`).join(", ");
  return (
    <section aria-label="Latency X-ray" className="stack" style={{ gap: "var(--space-2)" }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong style={{ fontSize: "var(--text-sm)" }}>🩻 Latency X-ray</strong>
        <span className="row">
          <span className="badge">db: {diagnostics.db_dialect}</span>
          <span className="badge badge-accent">total {fmt(diagnostics.total_ms)} ms</span>
        </span>
      </div>
      <div className="xray-bar" role="img" aria-label={`Search stages: ${summary}`}>
        {XRAY_STAGES.map((s) => (
          <span key={s.key} style={{ width: `${(diagnostics[s.key] / scale) * 100}%`, background: s.color }} />
        ))}
      </div>
      <ul className="xray-legend">
        {XRAY_STAGES.map((s) => (
          <li key={s.key}>
            <span className="swatch" style={{ background: s.color }} aria-hidden="true" />
            {s.label}: <strong>{fmt(diagnostics[s.key])} ms</strong>
          </li>
        ))}
        <li>
          Candidates {diagnostics.raw_candidates_count} → {diagnostics.deduped_blocks_count} parent blocks
        </li>
      </ul>
    </section>
  );
}
