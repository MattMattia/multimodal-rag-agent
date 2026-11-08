"use client";

import { useDemoStatus } from "../shell/StatusProvider";
import { StatusBadgeView } from "../shell/StatusBadge";

const yesNo = (value: boolean) => (value ? <span className="badge badge-success">yes</span> : <span className="badge">no</span>);

export function ServiceStatus() {
  const { status, error, refresh } = useDemoStatus();
  return (
    <section className="card stack" aria-label="Service status">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>📡 Service status & telemetry</h2>
        <button type="button" className="btn btn-sm" onClick={() => void refresh()}>
          ↻ Refresh
        </button>
      </div>
      <StatusBadgeView status={status} error={error} />
      {status && (
        <ul className="service-list">
          <li>
            <span>Database dialect</span>
            <span className="badge badge-accent">{status.db_dialect}</span>
          </li>
          <li>
            <span>Golden Corpus seeded</span>
            {yesNo(status.demo_seeded)}
          </li>
          <li>
            <span>Documents · chunks · images</span>
            <span>
              {status.total_documents} · {status.total_chunks} · {status.total_images}
            </span>
          </li>
          <li>
            <span>Gemini configured</span>
            {yesNo(status.gemini_configured)}
          </li>
          <li>
            <span>Embedding mode</span>
            <span className={`badge ${status.embedding_mode === "gemini" ? "badge-success" : "badge-warning"}`}>{status.embedding_mode}</span>
          </li>
          <li>
            <span>Langfuse tracing</span>
            {yesNo(status.langfuse_enabled)}
          </li>
          {Object.entries(status.active_models).map(([role, model]) => (
            <li key={role}>
              <span>Model · {role}</span>
              <code style={{ overflowWrap: "anywhere", textAlign: "right" }}>{model}</code>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
