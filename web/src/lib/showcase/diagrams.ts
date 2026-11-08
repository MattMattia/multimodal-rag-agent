/**
 * SVG renditions of the three Golden Corpus figures (the backend draws them as PNGs with Pillow in
 * `demo_seeder.py`). Served by `/api/documents/[id]/images/[imageId]` when the backend is offline.
 */
import type { GoldenImage } from "./corpus";

const FONT = "font-family='Inter,Segoe UI,Arial,sans-serif'";

function frame(title: string, body: string): string {
  return (
    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 900 520' width='900' height='520' role='img' aria-label='${title}'>` +
    `<rect width='900' height='520' fill='#ffffff'/>` +
    `<text x='450' y='40' text-anchor='middle' ${FONT} font-size='22' font-weight='700' fill='#111827'>${title}</text>` +
    `${body}</svg>`
  );
}

function box(x: number, y: number, w: number, h: number, label: string, fill: string): string {
  return (
    `<rect x='${x}' y='${y}' width='${w}' height='${h}' rx='10' fill='${fill}' stroke='#1f2937' stroke-width='2'/>` +
    `<text x='${x + w / 2}' y='${y + h / 2 + 6}' text-anchor='middle' ${FONT} font-size='16' fill='#111827'>${label}</text>`
  );
}

function arrow(x1: number, y1: number, x2: number, y2: number): string {
  return `<line x1='${x1}' y1='${y1}' x2='${x2}' y2='${y2}' stroke='#374151' stroke-width='2.5' marker-end='url(#a)'/>`;
}

function architecture(): string {
  const defs = "<defs><marker id='a' markerWidth='10' markerHeight='10' refX='9' refY='5' orient='auto'><path d='M0,0 L10,5 L0,10 z' fill='#374151'/></marker></defs>";
  return frame(
    "Microservices architecture - RAG system",
    defs +
      box(340, 70, 220, 50, "Client (Streamlit / Next.js)", "#dbeafe") +
      arrow(450, 120, 450, 160) +
      box(340, 160, 220, 50, "FastAPI API Gateway", "#e0e7ff") +
      arrow(400, 210, 170, 260) +
      arrow(450, 210, 450, 260) +
      arrow(500, 210, 730, 260) +
      box(60, 260, 220, 50, "Ingestion", "#dcfce7") +
      box(340, 260, 220, 50, "Hybrid Search", "#fef9c3") +
      box(620, 260, 220, 50, "Autonomous Agent", "#fce7f3") +
      arrow(170, 310, 400, 380) +
      arrow(450, 310, 450, 380) +
      arrow(730, 310, 500, 380) +
      box(290, 380, 320, 56, "PostgreSQL + pgvector (HNSW m=16)", "#e5e7eb") +
      box(680, 440, 180, 44, "Langfuse", "#ede9fe") +
      `<text x='450' y='480' text-anchor='middle' ${FONT} font-size='14' fill='#374151'>RRF k=60 + semantic reranker</text>`,
  );
}

function bars(): string {
  const data: Array<[string, number, string]> = [
    ["North America", 45, "#2563eb"],
    ["EMEA", 28, "#0d9488"],
    ["LATAM", 19, "#d97706"],
  ];
  const body = data
    .map(([label, value, color], i) => {
      const height = value * 8;
      const x = 170 + i * 220;
      const y = 450 - height;
      return (
        `<rect x='${x}' y='${y}' width='120' height='${height}' rx='6' fill='${color}'/>` +
        `<text x='${x + 60}' y='${y - 10}' text-anchor='middle' ${FONT} font-size='18' font-weight='700' fill='#111827'>$${value}M</text>` +
        `<text x='${x + 60}' y='478' text-anchor='middle' ${FONT} font-size='16' fill='#374151'>${label}</text>`
      );
    })
    .join("");
  return frame("Q3 revenue by region (USD millions) - total $92M", `<line x1='120' y1='450' x2='820' y2='450' stroke='#9ca3af' stroke-width='2'/>${body}`);
}

function matrix(): string {
  const colors = [
    ["#fde68a", "#fca5a5", "#f87171"],
    ["#bbf7d0", "#fde68a", "#fca5a5"],
    ["#86efac", "#bbf7d0", "#fde68a"],
  ];
  const labels: Record<string, string> = { "0,2": "A01 A03 A10", "1,1": "A04 A09" };
  let body = "";
  colors.forEach((row, r) =>
    row.forEach((fill, c) => {
      const x = 240 + c * 150;
      const y = 80 + r * 120;
      body += `<rect x='${x}' y='${y}' width='150' height='120' fill='${fill}' stroke='#ffffff' stroke-width='3'/>`;
      const label = labels[`${r},${c}`];
      if (label) body += `<text x='${x + 75}' y='${y + 66}' text-anchor='middle' ${FONT} font-size='16' font-weight='700' fill='#111827'>${label}</text>`;
    }),
  );
  body += `<text x='465' y='470' text-anchor='middle' ${FONT} font-size='16' fill='#374151'>Impact →</text>`;
  body += `<text x='200' y='260' text-anchor='middle' ${FONT} font-size='16' fill='#374151' transform='rotate(-90 200 260)'>Probability →</text>`;
  return frame("OWASP risk matrix (probability x impact)", body);
}

export function renderDiagramSvg(image: GoldenImage): string {
  switch (image.kind) {
    case "architecture":
      return architecture();
    case "bars":
      return bars();
    case "matrix":
      return matrix();
  }
}
