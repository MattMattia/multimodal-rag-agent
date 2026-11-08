"use client";

import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";
import type { EvaluationModeName, EvaluationResponse, ModeEvaluation } from "@/lib/contracts";
import { api } from "@/lib/client/api";
import { MODE_META, MetricChart } from "./MetricChart";

const ORDER: EvaluationModeName[] = ["dense", "sparse", "hybrid"];
const ratio = (v: number) => v.toFixed(3);
const ms = (v: number) => `${v.toFixed(v >= 100 ? 0 : 1)} ms`;

export function BenchmarkLab() {
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
      setReport(await api.evaluate(topK, controller.current.signal));
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) setError(e instanceof Error ? e.message : "Benchmark failed.");
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
        <h1>📊 Scientific RAG Evaluation & Benchmark Lab</h1>
        <p>
          8 golden queries (paraphrased and cross-lingual) over the Golden Corpus. Binary relevance: expected document plus an expected
          keyword in the chunk or its parent block. NDCG is recall-aware: the ideal ranking uses every relevant block in the corpus.
        </p>
      </header>

      <section className="card row" style={{ justifyContent: "space-between" }}>
        <div className="field" style={{ minWidth: 200 }}>
          <label htmlFor="bench-k">
            k (Hit Rate@k, MRR, NDCG@k): <strong>{topK}</strong>
          </label>
          <input id="bench-k" type="range" min={1} max={20} value={topK} onChange={(e) => setTopK(Number(e.target.value))} />
        </div>
        <button type="button" className="btn btn-primary" onClick={() => void run()} disabled={running}>
          {running ? <span className="spinner" aria-hidden="true" /> : "▶"} {running ? "Running 24 searches…" : "Run live benchmark"}
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
            <span className="badge">{report.num_queries} queries</span>
            <span className="badge">k = {report.top_k}</span>
          </div>
          {(report.warnings ?? []).map((w) => (
            <div key={w} className="alert alert-warning" role="note">
              ⚠️ {w}
            </div>
          ))}
          <ul className="legend" aria-label="Retrieval modes">
            {modes.map(({ mode, data }) => (
              <li key={mode}>
                <span className="swatch" style={{ background: MODE_META[mode].color }} aria-hidden="true" />
                {MODE_META[mode].label}
                {!data.semantic && <span className="badge badge-warning">not semantic</span>}
              </li>
            ))}
          </ul>
          <div className="metric-grid" aria-live="polite">
            <MetricChart title={`Hit Rate@${report.top_k}`} values={series((m) => m.hit_rate_at_k)} max={1} format={ratio} />
            <MetricChart title="MRR" values={series((m) => m.mrr)} max={1} format={ratio} />
            <MetricChart title={`NDCG@${report.top_k}`} values={series((m) => m.ndcg_at_k)} max={1} format={ratio} />
            <MetricChart title="Avg latency (ms)" values={series((m) => m.avg_latency_ms)} format={ms} />
          </div>

          <section className="card stack" aria-label="Per-query results">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2 style={{ margin: 0 }}>Per-query breakdown</h2>
              <div className="tabs" role="tablist" aria-label="Retrieval mode" style={{ margin: 0, border: "none" }} onKeyDown={onTabKeyDown}>
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
                      <th scope="col">Query</th>
                      <th scope="col">Category</th>
                      <th scope="col">Relevance @k</th>
                      <th scope="col" className="num">RR</th>
                      <th scope="col" className="num">NDCG</th>
                      <th scope="col" className="num">Latency</th>
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
                          <span className="rel-dots" aria-label={`Relevance ${q.relevances.join(", ") || "none"}`}>
                            {q.relevances.map((r, i) => (
                              <span key={i} data-rel={r} />
                            ))}
                          </span>
                          {q.hit ? " ✅" : " ❌"}
                        </td>
                        <td className="num">{q.reciprocal_rank.toFixed(2)}</td>
                        <td className="num">{q.ndcg.toFixed(2)}</td>
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
          <p style={{ margin: 0 }}>Run the benchmark to compare Dense only, Sparse only and Hybrid RRF + Reranker.</p>
        </div>
      )}
    </div>
  );
}
