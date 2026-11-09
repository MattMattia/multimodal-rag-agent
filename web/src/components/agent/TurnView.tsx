"use client";

import { formatNumber } from "@/lib/i18n/format";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import { Markdown } from "../Markdown";
import { CitationCard } from "./CitationCard";
import { LatencyXRay } from "./LatencyXRay";
import { ToolTimeline } from "./ToolTimeline";
import type { Turn } from "./types";

export function TurnView({ turn, onFeedback }: { turn: Turn; onFeedback: (turn: Turn, rating: 1 | -1) => void }) {
  const { locale, t } = useLocale();
  const streaming = turn.status === "streaming";
  return (
    <div className="message">
      <div className="message-user">{turn.question}</div>
      <div className="message-assistant stack" aria-busy={streaming}>
        <ToolTimeline steps={turn.steps} />
        {turn.answer ? (
          <div>
            <Markdown source={turn.answer} />
            {streaming && <span className="cursor" aria-hidden="true" />}
          </div>
        ) : (
          streaming && (
            <p className="subtle row" style={{ margin: 0 }}>
              <span className="spinner" aria-hidden="true" /> {t.agent.turn.reasoning}
            </p>
          )
        )}
        {/* Announced once when the answer completes, instead of on every streamed token. */}
        <p className="sr-only" aria-live="polite">
          {turn.status === "done" ? `${t.agent.turn.answerReady} ${turn.answer.slice(0, 300)}` : ""}
        </p>
        {turn.status === "error" && (
          <div className="alert alert-danger" role="alert">
            {turn.error}
          </div>
        )}
        {turn.diagnostics && <LatencyXRay diagnostics={turn.diagnostics} />}
        {turn.citations.length > 0 && (
          <section aria-label={t.agent.turn.citationsLabel} className="stack" style={{ gap: "var(--space-2)" }}>
            <strong style={{ fontSize: "var(--text-sm)" }}>{t.agent.turn.citationsTitle}</strong>
            <div className="citations">
              {turn.citations.map((c, i) => (
                <CitationCard key={`${c.chunk_id ?? i}`} citation={c} evidence={c.chunk_id ? turn.evidence[c.chunk_id] : undefined} />
              ))}
            </div>
          </section>
        )}
        {turn.status === "done" && (
          <div className="message-meta">
            {turn.duration_ms !== null && <span>⏱️ {formatNumber(locale, turn.duration_ms, 0)} ms</span>}
            {turn.source && (
              <span className={`badge ${turn.source === "fastapi" ? "badge-success" : "badge-warning"}`}>
                {turn.source === "fastapi" ? t.agent.turn.sourceLive : t.agent.turn.sourceShowcase}
              </span>
            )}
            <span className="row" style={{ marginLeft: "auto" }} role="group" aria-label={t.agent.turn.rate}>
              <button
                type="button"
                className="btn btn-sm icon-btn"
                aria-pressed={turn.feedback === 1}
                aria-label={t.agent.turn.helpful}
                disabled={!turn.message_id}
                onClick={() => onFeedback(turn, 1)}
              >
                👍
              </button>
              <button
                type="button"
                className="btn btn-sm icon-btn"
                aria-pressed={turn.feedback === -1}
                aria-label={t.agent.turn.notHelpful}
                disabled={!turn.message_id}
                onClick={() => onFeedback(turn, -1)}
              >
                👎
              </button>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
