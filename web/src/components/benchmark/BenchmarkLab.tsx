"use client";

import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import type { EvaluationModeName, EvaluationResponse, ModeEvaluation } from "@/lib/contracts";
import { api } from "@/lib/client/api";
import { formatMs, formatNumber } from "@/lib/i18n/format";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import { MODE_COLOR, MetricChart } from "./MetricChart";

const ORDER: EvaluationModeName[] = ["dense", "sparse", "hybrid"];

export function BenchmarkLab() {
  const { locale, t } = useLocale();
  const b = t.benchmark;
  const ratio = (v: number) => formatNumber(locale, v, 3);
  const ms = (v: number) => `${formatMs(locale, v)} ms`;
  const [topK, setTopK] = useState(5);
  const [report, setReport] = useState<EvaluationResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailMode, setDetailMode] = useState<EvaluationModeName>("hybrid");
  const controller = useRef<AbortController | null>(null);
  const tabsId = useId();

  useEffect(() => () => controller.current?.abort(), []);

  const run = async () => {
    controller.current?.abort();
    controller.current = new AbortController();
    setRunning(true);
    setError(null);
    try {
      setReport(await api.evaluate(topK, locale, controller.current.signal));
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) setError(e instanceof Error ? e.message : b.failed);
    } finally {
      setRunning(false);
    }
  };

  const modes = ORDER.flatMap((mode) => {
    const data = report?.modes[mode];
    return data ? [{ mode, data }] : [];
  });
  const series = (pick: (m: ModeEvaluation) => number) => modes.map(({ mode, data }) => ({ mode, value: pick(data) }));
  const detail = report?.modes[detailMode];

  /** WAI-ARIA tabs: arrow keys move focus and selection between the mode tabs (roving tabindex). */
  const onTabKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const available = modes.map((m) => m.mode);
    const index = available.indexOf(detailMode);
    const next = available[(index + (event.key === "ArrowRight" ? 1 : available.length - 1)) % available.length];
    if (!next) return;
    setDetailMode(next);
    document.getElementById(`${tabsId}-tab-${next}`)?.focus();
  };

  return (
    <div className="stack" style={{ gap: "var(--space-4)" }}>
      <header className="page-header">
        <h1>{b.title}</h1>
        <p>{b.intro}</p>
      </header>

      <section className="card row" style={{ justifyContent: "space-between" }}>
        <div className="field" style={{ minWidth: 200 }}>
          <label htmlFor="bench-k">
            {b.kLabel} <strong>{topK}</strong>
          </label>
          <input id="bench-k" type="range" min={1} max={20} value={topK} onChange={(e) => setTopK(Number(e.target.value))} />
        </div>
        <button type="button" className="btn btn-primary" onClick={() => void run()} disabled={running}>
          {running ? <span className="spinner" aria-hidden="true" /> : "▶"} {running ? b.running : b.run}
        </button>
      </section>

      {error && (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      )}

      {report && (
        <>
          <div className="row">
            <span className={`badge ${report.embedding_mode === "gemini" ? "badge-success" : "badge-warning"}`}>
              embedding_mode: {report.embedding_mode}
            </span>
            <span className="badge">{b.queries(report.num_queries)}</span>
            <span className="badge">k = {report.top_k}</span>
          </div>
          {(report.warnings ?? []).map((w) => (
            <div key={w} className="alert alert-warning" role="note">
              ⚠️ {w}
            </div>
          ))}
          <ul className="legend" aria-label={b.modesLabel}>
            {modes.map(({ mode, data }) => (
              <li key={mode}>
                <span className="swatch" style={{ background: MODE_COLOR[mode] }} aria-hidden="true" />
                {b.modeLabels[mode]}
                {!data.semantic && <span className="badge badge-warning">{b.notSemantic}</span>}
              </li>
            ))}
          </ul>
          <div className="metric-grid" aria-live="polite">
            <MetricChart title={b.hitRate(report.top_k)} values={series((m) => m.hit_rate_at_k)} max={1} format={ratio} />
            <MetricChart title={b.mrr} values={series((m) => m.mrr)} max={1} format={ratio} />
            <MetricChart title={b.ndcg(report.top_k)} values={series((m) => m.ndcg_at_k)} max={1} format={ratio} />
            <MetricChart title={b.avgLatency} values={series((m) => m.avg_latency_ms)} format={ms} />
          </div>

          <section className="card stack" aria-label={b.perQueryLabel}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2 style={{ margin: 0 }}>{b.perQueryTitle}</h2>
              <div className="tabs" role="tablist" aria-label={b.modeTabs} style={{ margin: 0, border: "none" }} onKeyDown={onTabKeyDown}>
                {modes.map(({ mode }) => (
                  <button
                    key={mode}
                    id={`${tabsId}-tab-${mode}`}
                    type="button"
                    role="tab"
                    className="tab"
                    aria-selected={detailMode === mode}
                    aria-controls={`${tabsId}-panel`}
                    tabIndex={detailMode === mode ? 0 : -1}
                    onClick={() => setDetailMode(mode)}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>
            {detail && (
              <div
                className="table-wrap"
                id={`${tabsId}-panel`}
                role="tabpanel"
                aria-labelledby={`${tabsId}-tab-${detailMode}`}
                tabIndex={0}
              >
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">{b.columns.query}</th>
                      <th scope="col">{b.columns.category}</th>
                      <th scope="col">{b.columns.relevance}</th>
                      <th scope="col" className="num">{b.columns.rr}</th>
                      <th scope="col" className="num">{b.columns.ndcg}</th>
                      <th scope="col" className="num">{b.columns.latency}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.per_query.map((q) => (
                      <tr key={q.id}>
                        <td>
                          <strong>{q.id}</strong> {q.query}
                        </td>
                        <td>
                          <span className="badge">{q.category}</span>
                        </td>
                        <td>
                          <span className="rel-dots" aria-label={b.relevance(q.relevances.join(", ") || b.none)}>
                            {q.relevances.map((r, i) => (
                              <span key={i} data-rel={r} />
                            ))}
                          </span>
                          {q.hit ? " ✅" : " ❌"}
                        </td>
                        <td className="num">{formatNumber(locale, q.reciprocal_rank, 2)}</td>
                        <td className="num">{formatNumber(locale, q.ndcg, 2)}</td>
                        <td className="num">{ms(q.latency_ms)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
      {!report && !running && (
        <div className="card empty-state">
          <p style={{ margin: 0 }}>{b.empty}</p>
        </div>
      )}
    </div>
  );
}
