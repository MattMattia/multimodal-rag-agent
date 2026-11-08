"use client";

import { type FormEvent, type KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DocumentResponse, ExportFormat, ExportTranscriptMessage, SessionSummary } from "@/lib/contracts";
import { api, downloadBlob } from "@/lib/client/api";
import { HyperparameterPanel } from "./HyperparameterPanel";
import { SessionsSidebar } from "./SessionsSidebar";
import { TurnView } from "./TurnView";
import { DEFAULT_HYPERPARAMETERS, type Hyperparameters } from "./types";
import { useAgentChat } from "./useAgentChat";

export function AgentStudio() {
  const chat = useAgentChat();
  const [params, setParams] = useState<Hyperparameters>(DEFAULT_HYPERPARAMETERS);
  const [filterDocumentId, setFilterDocumentId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [remoteSessions, setRemoteSessions] = useState<SessionSummary[]>([]);
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  const loadSessions = useCallback(async () => {
    setRemoteSessions(await api.sessions().catch(() => []));
  }, []);

  useEffect(() => {
    void loadSessions();
    api.documents().then(setDocuments, () => setDocuments([]));
  }, [loadSessions]);

  const lastTurn = chat.session.turns.at(-1);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [chat.session.turns.length, lastTurn?.status]);

  useEffect(() => {
    if (lastTurn?.status === "done") void loadSessions();
  }, [lastTurn?.status, loadSessions]);

  /** Server sessions plus the ones that exist only in this tab (showcase mode keeps no server state). */
  const sessions = useMemo<SessionSummary[]>(() => {
    const known = new Set(remoteSessions.map((s) => s.session_id));
    const current = chat.session.id && chat.session.turns.length ? { [chat.session.id]: chat.session } : {};
    const local = Object.values({ ...chat.localSessions, ...current })
      .filter((s) => s.id && !known.has(s.id))
      .map((s) => ({
        session_id: s.id as string,
        title: s.title,
        created_at: s.turns[0]?.created_at ?? new Date().toISOString(),
        updated_at: s.turns.at(-1)?.created_at ?? new Date().toISOString(),
        message_count: s.turns.length * 2,
      }));
    return [...local, ...remoteSessions];
  }, [chat.localSessions, chat.session, remoteSessions]);

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    const message = draft;
    setDraft("");
    void chat.send(message, params, filterDocumentId);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) submit(event);
  };

  const exportSession = async (format: ExportFormat) => {
    if (!chat.session.id) return;
    const messages: ExportTranscriptMessage[] = chat.session.turns.flatMap((t) => [
      { role: "user", content: t.question, created_at: t.created_at },
      {
        role: "assistant",
        content: t.answer,
        created_at: t.created_at,
        citations: t.citations,
        executed_tools: t.steps.map((s) => ({ tool_name: s.tool_name })),
      },
    ]);
    try {
      const { blob, filename } = await api.exportSession(chat.session.id, format, messages);
      downloadBlob(blob, filename);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Export failed.");
    }
  };

  const deleteSession = async (id: string) => {
    try {
      await api.deleteSession(id);
      chat.forget(id);
      await loadSessions();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not delete the session.");
    }
  };

  const openSession = async (id: string) => {
    try {
      await chat.open(id, { ...params, filter_document_id: filterDocumentId });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not load the session.");
    }
  };

  return (
    <div className="studio">
      <SessionsSidebar
        sessions={sessions}
        activeId={chat.session.id}
        documents={documents}
        filterDocumentId={filterDocumentId}
        busy={chat.busy}
        canExport={Boolean(chat.session.id) && !chat.busy}
        onNew={chat.reset}
        onOpen={(id) => void openSession(id)}
        onDelete={(id) => void deleteSession(id)}
        onExport={(format) => void exportSession(format)}
        onFilter={setFilterDocumentId}
        onQuickPrompt={(prompt) => void chat.send(prompt, params, filterDocumentId)}
      />

      <section className="chat" aria-label="Conversation">
        {notice && (
          <div className="alert alert-danger row" role="alert" style={{ justifyContent: "space-between" }}>
            {notice}
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setNotice(null)}>
              Dismiss
            </button>
          </div>
        )}
        <div className="thread">
          {chat.session.turns.length === 0 ? (
            <div className="card empty-state">
              <div>
                <p style={{ fontSize: "2rem", margin: 0 }} aria-hidden="true">
                  🤖
                </p>
                <h1 style={{ fontSize: "var(--text-lg)", margin: "var(--space-2) 0" }}>Autonomous ReAct Agent Studio</h1>
                <p style={{ margin: 0, maxWidth: "52ch" }}>
                  Ask about the Golden Corpus — architecture, Q3 financials or Zero Trust security. Watch every tool call, the
                  latency X-ray of each RAG stage and the multimodal evidence behind the answer.
                </p>
              </div>
            </div>
          ) : (
            chat.session.turns.map((turn) => <TurnView key={turn.id} turn={turn} onFeedback={(t, r) => void chat.rate(t, r)} />)
          )}
          <div ref={endRef} />
        </div>
        <form className="composer" onSubmit={submit} aria-label="Ask the agent">
          <label htmlFor="composer-input" className="sr-only">
            Message
          </label>
          <textarea
            id="composer-input"
            className="textarea"
            placeholder="Ask the agent… e.g. “Generate a PDF report on Q3 revenue by region”"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            maxLength={8000}
            rows={2}
          />
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="kbd-hint">Enter to send · Shift+Enter for a new line</span>
            {chat.busy ? (
              <button type="button" className="btn" onClick={chat.stop}>
                ⏹ Stop
              </button>
            ) : (
              <button type="submit" className="btn btn-primary" disabled={!draft.trim()}>
                Send ➤
              </button>
            )}
          </div>
        </form>
      </section>

      <div className="params">
        <HyperparameterPanel value={params} onChange={setParams} disabled={chat.busy} />
      </div>
    </div>
  );
}
