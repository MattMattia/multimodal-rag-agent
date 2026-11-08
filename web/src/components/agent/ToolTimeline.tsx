import type { ToolStep } from "./types";

const TOOL_ICONS: Record<string, string> = {
  search_knowledge_base: "🔎",
  generate_report_pdf: "📄",
  dispatch_webhook: "📡",
};

/** Animated timeline of the agent's tool calls (`tool_start` → `tool_end`, with duration in ms). */
export function ToolTimeline({ steps }: { steps: readonly ToolStep[] }) {
  if (steps.length === 0) return null;
  return (
    <ol className="timeline" aria-label="Tool execution timeline">
      {steps.map((step) => (
        <li key={step.id} data-state={step.state}>
          <span aria-hidden="true">{TOOL_ICONS[step.tool_name] ?? "🛠️"}</span>
          <span className="tool-name">{step.tool_name}</span>
          {step.state === "running" ? (
            <span className="badge badge-warning">
              <span className="spinner" aria-hidden="true" /> running
            </span>
          ) : (
            <span className="badge badge-success">
              {step.duration_ms === null ? "done" : `${step.duration_ms.toFixed(step.duration_ms >= 100 ? 0 : 1)} ms`}
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
