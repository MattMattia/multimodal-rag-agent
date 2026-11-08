import type { EvaluationModeName } from "@/lib/contracts";

export const MODE_META: Record<EvaluationModeName, { label: string; color: string }> = {
  dense: { label: "Dense only", color: "var(--series-dense)" },
  sparse: { label: "Sparse BM25 only", color: "var(--series-sparse)" },
  hybrid: { label: "Hybrid RRF + Reranker", color: "var(--series-hybrid)" },
};

interface Props {
  title: string;
  values: Array<{ mode: EvaluationModeName; value: number }>;
  /** Fixed maximum (e.g. 1 for ratios); defaults to the largest value. */
  max?: number;
  format: (value: number) => string;
}

const WIDTH = 320;
const HEIGHT = 190;
const PAD_BOTTOM = 28;
const PAD_TOP = 22;

/** Accessible SVG bar chart comparing one metric across the three retrieval modes. */
export function MetricChart({ title, values, max, format }: Props) {
  const top = max ?? Math.max(...values.map((v) => v.value), 1e-9);
  const slot = WIDTH / values.length;
  const barWidth = Math.min(64, slot * 0.6);
  const plot = HEIGHT - PAD_BOTTOM - PAD_TOP;
  const description = values.map((v) => `${MODE_META[v.mode].label}: ${format(v.value)}`).join("; ");
  return (
    <figure className="card" style={{ margin: 0 }}>
      <figcaption>
        <h3>{title}</h3>
      </figcaption>
      <svg className="chart" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`${title}. ${description}`}>
        <line className="axis" x1={0} x2={WIDTH} y1={HEIGHT - PAD_BOTTOM} y2={HEIGHT - PAD_BOTTOM} />
        {values.map((v, i) => {
          const h = top > 0 ? (v.value / top) * plot : 0;
          const x = i * slot + (slot - barWidth) / 2;
          const y = HEIGHT - PAD_BOTTOM - h;
          return (
            <g key={v.mode}>
              <rect x={x} y={y} width={barWidth} height={Math.max(h, 1)} rx={6} fill={MODE_META[v.mode].color}>
                <title>{`${MODE_META[v.mode].label}: ${format(v.value)}`}</title>
              </rect>
              <text className="value" x={x + barWidth / 2} y={y - 6} textAnchor="middle">
                {format(v.value)}
              </text>
              <text x={x + barWidth / 2} y={HEIGHT - 8} textAnchor="middle">
                {v.mode}
              </text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}
