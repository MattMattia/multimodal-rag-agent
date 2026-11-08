"use client";

import { useState } from "react";

type ModeId = "cloud" | "local" | "enterprise";

interface MapNode {
  id: string;
  label: string;
  sub: string;
  x: number;
  y: number;
  detail: string;
}

const NODES: MapNode[] = [
  { id: "browser", label: "Browser", sub: "recruiter / engineer", x: 20, y: 20, detail: "Talks only to the Next.js BFF under /api/*. It never sees the backend URL or key." },
  { id: "next", label: "Next.js 15 BFF", sub: "Vercel · Route Handlers", x: 250, y: 20, detail: "Server-only proxy with a short timeout per call. Falls back to the showcase engine when FastAPI is unreachable." },
  { id: "showcase", label: "Showcase Engine", sub: "embedded Golden Corpus", x: 480, y: 20, detail: "TypeScript corpus, lexical-hashing dense stand-in + BM25, RRF k=60, SSE stream, PDF reports, benchmark." },
  { id: "streamlit", label: "Streamlit", sub: ":8501 dashboard", x: 20, y: 150, detail: "Operator dashboard of the full stack (sessions, tuning, corpus, benchmark)." },
  { id: "fastapi", label: "FastAPI /api/v1", sub: "ReAct agent · hybrid search", x: 250, y: 150, detail: "X-API-Key auth, sliding-window rate limit, Gemini agent with tools, SearchDiagnostics per stage." },
  { id: "gemini", label: "Gemini", sub: "agent · vision · embeddings", x: 480, y: 150, detail: "LLM reasoning, Vision descriptions of diagrams and 768-d embeddings (mock vectors without an API key)." },
  { id: "postgres", label: "PostgreSQL 16", sub: "pgvector HNSW + GIN", x: 130, y: 280, detail: "HNSW m=16, ef_construction=64 for vectors and full-text GIN for BM25-style ranking." },
  { id: "sqlite", label: "SQLite fallback", sub: "aiosqlite · exact search", x: 370, y: 280, detail: "Zero-Docker mode: exact cosine in Python plus BM25, auto-seeded Golden Corpus in under a second." },
  { id: "langfuse", label: "Langfuse v2", sub: ":3000 traces", x: 560, y: 280, detail: "Traces of every agent turn, tool call and retrieval span." },
];

const EDGES: Array<[string, string]> = [
  ["browser", "next"],
  ["next", "showcase"],
  ["next", "fastapi"],
  ["streamlit", "fastapi"],
  ["fastapi", "gemini"],
  ["fastapi", "postgres"],
  ["fastapi", "sqlite"],
  ["fastapi", "langfuse"],
];

const MODES: Record<ModeId, { title: string; caption: string; nodes: string[] }> = {
  cloud: {
    title: "1 · Cloud Showcase",
    caption: "Vercel 24/7 serverless: the BFF answers from the embedded engine when the backend is off.",
    nodes: ["browser", "next", "showcase"],
  },
  local: {
    title: "2 · Zero-Docker Local",
    caption: "python run.py: FastAPI on SQLite with exact vector search, BM25 and an auto-seeded corpus.",
    nodes: ["browser", "next", "streamlit", "fastapi", "sqlite", "gemini"],
  },
  enterprise: {
    title: "3 · Full Enterprise",
    caption: "Docker Compose: PostgreSQL + pgvector, FastAPI, Gemini, Langfuse, Streamlit and Next.js.",
    nodes: ["browser", "next", "streamlit", "fastapi", "gemini", "postgres", "langfuse"],
  },
};

const W = 160;
const H = 64;
const center = (n: MapNode) => ({ x: n.x + W / 2, y: n.y + H / 2 });

/** Interactive tri-modal architecture map: pick an execution mode, then a component for details. */
export function TriModalMap() {
  const [mode, setMode] = useState<ModeId>("cloud");
  const [focus, setFocus] = useState<string>("next");
  const active = new Set(MODES[mode].nodes);
  const selected = NODES.find((n) => n.id === focus) ?? NODES[1]!;

  return (
    <section className="card stack" aria-label="Tri-modal architecture map">
      <h2>🗺️ Tri-modal architecture</h2>
      <div className="mode-switch" role="group" aria-label="Execution mode">
        {(Object.keys(MODES) as ModeId[]).map((id) => (
          <button key={id} type="button" aria-pressed={mode === id} onClick={() => setMode(id)}>
            {MODES[id].title}
          </button>
        ))}
      </div>
      <p className="subtle" style={{ margin: 0 }}>
        {MODES[mode].caption}
      </p>
      <svg className="arch-map" viewBox="0 0 740 360" role="group" aria-label={`Components active in ${MODES[mode].title}`}>
        {EDGES.map(([from, to]) => {
          const a = center(NODES.find((n) => n.id === from)!);
          const b = center(NODES.find((n) => n.id === to)!);
          return <line key={`${from}-${to}`} className="edge" x1={a.x} y1={a.y} x2={b.x} y2={b.y} data-active={active.has(from) && active.has(to)} />;
        })}
        {NODES.map((node) => (
          <g
            key={node.id}
            className="node"
            data-active={active.has(node.id)}
            role="button"
            tabIndex={0}
            aria-pressed={focus === node.id}
            aria-label={`${node.label}: ${node.sub}${active.has(node.id) ? "" : " (inactive in this mode)"}`}
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
              {node.label}
            </text>
            <text className="sub" x={node.x + W / 2} y={node.y + 46} textAnchor="middle">
              {node.sub}
            </text>
          </g>
        ))}
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
