"use client";

import type { SearchDiagnostics } from "@/lib/contracts";
import { formatMs } from "@/lib/i18n/format";
import { useLocale } from "@/lib/i18n/LocaleProvider";

export const XRAY_STAGES = [
  { key: "embedding_ms", color: "var(--stage-embedding)" },
  { key: "dense_ms", color: "var(--stage-dense)" },
  { key: "sparse_ms", color: "var(--stage-sparse)" },
  { key: "rrf_fusion_ms", color: "var(--stage-fusion)" },
  { key: "rerank_ms", color: "var(--stage-rerank)" },
] as const;

/** Latency X-ray of one RAG search (`SearchDiagnostics`): a stacked bar of every pipeline stage in ms. */
export function LatencyXRay({ diagnostics }: { diagnostics: SearchDiagnostics }) {
  const { locale, t } = useLocale();
  const fmt = (ms: number) => formatMs(locale, ms, true);
  const label = (key: (typeof XRAY_STAGES)[number]["key"]) => t.agent.xray.stages[key];
  const stagesTotal = XRAY_STAGES.reduce((sum, s) => sum + diagnostics[s.key], 0);
  const scale = stagesTotal > 0 ? stagesTotal : 1;
  const summary = XRAY_STAGES.map((s) => `${label(s.key)} ${fmt(diagnostics[s.key])} ms`).join(", ");
  return (
    <section aria-label={t.agent.xray.label} className="stack" style={{ gap: "var(--space-2)" }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong style={{ fontSize: "var(--text-sm)" }}>{t.agent.xray.title}</strong>
        <span className="row">
          <span className="badge">db: {diagnostics.db_dialect}</span>
          <span className="badge badge-accent">{t.agent.xray.total(fmt(diagnostics.total_ms))}</span>
        </span>
      </div>
      <div className="xray-bar" role="img" aria-label={t.agent.xray.summary(summary)}>
        {XRAY_STAGES.map((s) => (
          <span key={s.key} style={{ width: `${(diagnostics[s.key] / scale) * 100}%`, background: s.color }} />
        ))}
      </div>
      <ul className="xray-legend">
        {XRAY_STAGES.map((s) => (
          <li key={s.key}>
            <span className="swatch" style={{ background: s.color }} aria-hidden="true" />
            {label(s.key)}: <strong>{fmt(diagnostics[s.key])} ms</strong>
          </li>
        ))}
        <li>{t.agent.xray.candidates(diagnostics.raw_candidates_count, diagnostics.deduped_blocks_count)}</li>
      </ul>
    </section>
  );
}
