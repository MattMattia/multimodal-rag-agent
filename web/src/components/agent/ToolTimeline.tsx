"use client";

import { formatNumber } from "@/lib/i18n/format";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import type { ToolStep } from "./types";

const TOOL_ICONS: Record<string, string> = {
  search_knowledge_base: "🔎",
  generate_report_pdf: "📄",
  dispatch_webhook: "📡",
};

/** Animated timeline of the agent's tool calls (`tool_start` → `tool_end`, with duration in ms). */
export function ToolTimeline({ steps }: { steps: readonly ToolStep[] }) {
  const { locale, t } = useLocale();
  if (steps.length === 0) return null;
  return (
    <ol className="timeline" aria-label={t.agent.timeline.label}>
      {steps.map((step) => (
        <li key={step.id} data-state={step.state}>
          <span aria-hidden="true">{TOOL_ICONS[step.tool_name] ?? "🛠️"}</span>
          <span className="tool-name">{step.tool_name}</span>
          {step.state === "running" ? (
            <span className="badge badge-warning">
              <span className="spinner" aria-hidden="true" /> {t.agent.timeline.running}
            </span>
          ) : (
            <span className="badge badge-success">
              {step.duration_ms === null
                ? t.agent.timeline.done
                : `${formatNumber(locale, step.duration_ms, step.duration_ms >= 100 ? 0 : 1)} ms`}
            </span>
          )}
          {typeof step.tool_input?.query === "string" && (
            <span className="subtle" style={{ overflowWrap: "anywhere" }}>
              “{step.tool_input.query}”
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}
