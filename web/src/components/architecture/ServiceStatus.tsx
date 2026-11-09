"use client";

import { useLocale } from "@/lib/i18n/LocaleProvider";
import { useDemoStatus } from "../shell/StatusProvider";
import { StatusBadgeView } from "../shell/StatusBadge";

export function ServiceStatus() {
  const { status, error, refresh } = useDemoStatus();
  const { t } = useLocale();
  const s = t.architecture.service;
  const yesNo = (value: boolean) => (value ? <span className="badge badge-success">{s.yes}</span> : <span className="badge">{s.no}</span>);
  return (
    <section className="card stack" aria-label={s.label}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>{s.title}</h2>
        <button type="button" className="btn btn-sm" onClick={() => void refresh()}>
          {s.refresh}
        </button>
      </div>
      <StatusBadgeView status={status} error={error} />
      {status && (
        <ul className="service-list">
          <li>
            <span>{s.dialect}</span>
            <span className="badge badge-accent">{status.db_dialect}</span>
          </li>
          <li>
            <span>{s.seeded}</span>
            {yesNo(status.demo_seeded)}
          </li>
          <li>
            <span>{s.counts}</span>
            <span>
              {status.total_documents} · {status.total_chunks} · {status.total_images}
            </span>
          </li>
          <li>
            <span>{s.gemini}</span>
            {yesNo(status.gemini_configured)}
          </li>
          <li>
            <span>{s.embedding}</span>
            <span className={`badge ${status.embedding_mode === "gemini" ? "badge-success" : "badge-warning"}`}>{status.embedding_mode}</span>
          </li>
          <li>
            <span>{s.langfuse}</span>
            {yesNo(status.langfuse_enabled)}
          </li>
          {Object.entries(status.active_models).map(([role, model]) => (
            <li key={role}>
              <span>{s.model(role)}</span>
              <code style={{ overflowWrap: "anywhere", textAlign: "right" }}>{model}</code>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
