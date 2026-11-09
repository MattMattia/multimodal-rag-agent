"use client";

import { useState } from "react";
import { useLocale } from "@/lib/i18n/LocaleProvider";

type ModeId = "cloud" | "local" | "enterprise";
type NodeId = "browser" | "next" | "showcase" | "streamlit" | "fastapi" | "gemini" | "postgres" | "sqlite" | "langfuse";

interface MapNode {
  id: NodeId;
  x: number;
  y: number;
}

/** Layout only; labels, subtitles and details come from the active dictionary (`architecture.map.nodes`). */
const NODES: MapNode[] = [
  { id: "browser", x: 20, y: 20 },
  { id: "next", x: 250, y: 20 },
  { id: "showcase", x: 480, y: 20 },
  { id: "streamlit", x: 20, y: 150 },
  { id: "fastapi", x: 250, y: 150 },
  { id: "gemini", x: 480, y: 150 },
  { id: "postgres", x: 130, y: 280 },
  { id: "sqlite", x: 370, y: 280 },
  { id: "langfuse", x: 560, y: 280 },
];

const EDGES: Array<[NodeId, NodeId]> = [
  ["browser", "next"],
  ["next", "showcase"],
  ["next", "fastapi"],
  ["streamlit", "fastapi"],
  ["fastapi", "gemini"],
  ["fastapi", "postgres"],
  ["fastapi", "sqlite"],
  ["fastapi", "langfuse"],
];

const MODE_NODES: Record<ModeId, NodeId[]> = {
  cloud: ["browser", "next", "showcase"],
  local: ["browser", "next", "streamlit", "fastapi", "sqlite", "gemini"],
  enterprise: ["browser", "next", "streamlit", "fastapi", "gemini", "postgres", "langfuse"],
};

const W = 160;
const H = 64;
const center = (n: MapNode) => ({ x: n.x + W / 2, y: n.y + H / 2 });

/** Interactive tri-modal architecture map: pick an execution mode, then a component for details. */
export function TriModalMap() {
  const { t } = useLocale();
  const m = t.architecture.map;
  const [mode, setMode] = useState<ModeId>("cloud");
  const [focus, setFocus] = useState<NodeId>("next");
  const active = new Set<NodeId>(MODE_NODES[mode]);
  const selected = m.nodes[focus];

  return (
    <section className="card stack" aria-label={m.label}>
      <h2>{m.title}</h2>
      <div className="mode-switch" role="group" aria-label={m.modeGroup}>
        {(Object.keys(MODE_NODES) as ModeId[]).map((id) => (
          <button key={id} type="button" aria-pressed={mode === id} onClick={() => setMode(id)}>
            {m.modes[id].title}
          </button>
        ))}
      </div>
      <p className="subtle" style={{ margin: 0 }}>
        {m.modes[mode].caption}
      </p>
      <svg className="arch-map" viewBox="0 0 740 360" role="group" aria-label={m.activeIn(m.modes[mode].title)}>
        {EDGES.map(([from, to]) => {
          const a = center(NODES.find((n) => n.id === from)!);
          const b = center(NODES.find((n) => n.id === to)!);
          return <line key={`${from}-${to}`} className="edge" x1={a.x} y1={a.y} x2={b.x} y2={b.y} data-active={active.has(from) && active.has(to)} />;
        })}
        {NODES.map((node) => {
          const text = m.nodes[node.id];
          return (
            <g
              key={node.id}
              className="node"
              data-active={active.has(node.id)}
              role="button"
              tabIndex={0}
              aria-pressed={focus === node.id}
              aria-label={`${text.label}: ${text.sub}${active.has(node.id) ? "" : m.inactive}`}
              onClick={() => setFocus(node.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setFocus(node.id);
                }
              }}
              style={{ cursor: "pointer" }}
            >
              <rect x={node.x} y={node.y} width={W} height={H} rx={12} />
              <text x={node.x + W / 2} y={node.y + 28} textAnchor="middle">
                {text.label}
              </text>
              <text className="sub" x={node.x + W / 2} y={node.y + 46} textAnchor="middle">
                {text.sub}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="card card-subtle" aria-live="polite">
        <strong>{selected.label}</strong>
        <p className="muted" style={{ margin: "var(--space-1) 0 0" }}>
          {selected.detail}
        </p>
      </div>
    </section>
  );
}
