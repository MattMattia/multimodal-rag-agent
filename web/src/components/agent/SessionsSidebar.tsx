"use client";

import type { DocumentResponse, ExportFormat, SessionSummary } from "@/lib/contracts";
import { formatDate } from "@/lib/i18n/format";
import { useLocale } from "@/lib/i18n/LocaleProvider";

interface Props {
  sessions: readonly SessionSummary[];
  activeId: string | null;
  documents: readonly DocumentResponse[];
  filterDocumentId: string | null;
  busy: boolean;
  canExport: boolean;
  onNew: () => void;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onExport: (format: ExportFormat) => void;
  onFilter: (id: string | null) => void;
  /** Receives the prompt in the active language: it is shown and sent exactly as displayed. */
  onQuickPrompt: (prompt: string) => void;
}

export function SessionsSidebar(props: Props) {
  const { sessions, activeId, documents, filterDocumentId, busy } = props;
  const { locale, t } = useLocale();
  const s = t.agent.sidebar;
  return (
    <aside className="sidebar stack" aria-label={s.label}>
      <section className="card stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>{s.sessions}</h2>
          <button type="button" className="btn btn-sm btn-primary" onClick={props.onNew} disabled={busy}>
            {s.newSession}
          </button>
        </div>
        {sessions.length === 0 ? (
          <p className="subtle" style={{ margin: 0 }}>
            {s.empty}
          </p>
        ) : (
          <ul className="session-list">
            {sessions.map((session) => (
              <li key={session.session_id} className="session-item" aria-current={session.session_id === activeId ? "true" : undefined}>
                <button type="button" className="session-open" onClick={() => props.onOpen(session.session_id)} disabled={busy}>
                  <span>{session.title || s.untitled}</span>
                  <span className="subtle">
                    {s.messages(session.message_count)} · {formatDate(locale, session.updated_at)}
                  </span>
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm icon-btn"
                  aria-label={s.deleteSession(session.title)}
                  onClick={() => props.onDelete(session.session_id)}
                  disabled={busy}
                >
                  🗑️
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="row" role="group" aria-label={s.exportGroup}>
          <button type="button" className="btn btn-sm" disabled={!props.canExport} onClick={() => props.onExport("markdown")}>
            {s.exportMarkdown}
          </button>
          <button type="button" className="btn btn-sm" disabled={!props.canExport} onClick={() => props.onExport("pdf")}>
            {s.exportPdf}
          </button>
        </div>
      </section>

      <section className="card stack">
        <div className="field">
          <label htmlFor="doc-filter">{s.documentFilter}</label>
          <select id="doc-filter" className="select" value={filterDocumentId ?? ""} onChange={(e) => props.onFilter(e.target.value || null)}>
            <option value="">{s.allDocuments}</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.filename}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="card stack">
        <h2 style={{ margin: 0 }}>{s.quickPromptsTitle}</h2>
        <div className="quick-prompts">
          {t.agent.quickPrompts.map((p) => (
            <button key={p} type="button" className="chip" disabled={busy} onClick={() => props.onQuickPrompt(p)}>
              {p}
            </button>
          ))}
        </div>
      </section>
    </aside>
  );
}
