import type { DocumentResponse, ExportFormat, SessionSummary } from "@/lib/contracts";

export const QUICK_PROMPTS = [
  "What HNSW parameters does the vector index use (m, ef_construction)?",
  "How much revenue did North America bring in Q3? Show the regional table.",
  "How does the system stop a webhook from reaching internal IPs (SSRF)?",
  "Describe the microservices architecture diagram and how services reach the database.",
  "Generate a PDF report on GlobalTech's EBITDA and inference costs.",
] as const;

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
  onQuickPrompt: (prompt: string) => void;
}

export function SessionsSidebar(props: Props) {
  const { sessions, activeId, documents, filterDocumentId, busy } = props;
  return (
    <aside className="sidebar stack" aria-label="Sessions and evaluator tools">
      <section className="card stack">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>🗂️ Sessions</h2>
          <button type="button" className="btn btn-sm btn-primary" onClick={props.onNew} disabled={busy}>
            + New
          </button>
        </div>
        {sessions.length === 0 ? (
          <p className="subtle" style={{ margin: 0 }}>
            No saved sessions yet.
          </p>
        ) : (
          <ul className="session-list">
            {sessions.map((s) => (
              <li key={s.session_id} className="session-item" aria-current={s.session_id === activeId ? "true" : undefined}>
                <button type="button" className="session-open" onClick={() => props.onOpen(s.session_id)} disabled={busy}>
                  <span>{s.title || "Untitled session"}</span>
                  <span className="subtle">
                    {s.message_count} messages · {new Date(s.updated_at).toLocaleDateString()}
                  </span>
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm icon-btn"
                  aria-label={`Delete session ${s.title}`}
                  onClick={() => props.onDelete(s.session_id)}
                  disabled={busy}
                >
                  🗑️
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="row" role="group" aria-label="Export current session">
          <button type="button" className="btn btn-sm" disabled={!props.canExport} onClick={() => props.onExport("markdown")}>
            ⬇️ Markdown
          </button>
          <button type="button" className="btn btn-sm" disabled={!props.canExport} onClick={() => props.onExport("pdf")}>
            ⬇️ PDF
          </button>
        </div>
      </section>

      <section className="card stack">
        <div className="field">
          <label htmlFor="doc-filter">📄 Document filter</label>
          <select
            id="doc-filter"
            className="select"
            value={filterDocumentId ?? ""}
            onChange={(e) => props.onFilter(e.target.value || null)}
          >
            <option value="">All documents</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.filename}
              </option>
            ))}
          </select>
        </div>
      </section>

      <section className="card stack">
        <h2 style={{ margin: 0 }}>⚡ Quick prompts for evaluators</h2>
        <div className="quick-prompts">
          {QUICK_PROMPTS.map((p) => (
            <button key={p} type="button" className="chip" disabled={busy} onClick={() => props.onQuickPrompt(p)}>
              {p}
            </button>
          ))}
        </div>
      </section>
    </aside>
  );
}
