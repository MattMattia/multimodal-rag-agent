"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AgentStreamEvent,
  ChatMessageResponse,
  CitationItem,
  SearchDiagnostics,
  SearchResultItem,
} from "@/lib/contracts";
import { api } from "@/lib/client/api";
import { readAgentStream } from "@/lib/client/sse";
import type { ChatSession, Hyperparameters, ToolStep, Turn } from "./types";

const newId = (): string => crypto.randomUUID();
const EMPTY_SESSION: ChatSession = { id: null, title: "New session", turns: [] };

/** Pure reducer step: applies one SSE event to a turn and returns the new turn. */
export function applyEvent(turn: Turn, event: AgentStreamEvent): Turn {
  switch (event.type) {
    case "tool_start":
      return {
        ...turn,
        steps: [
          ...turn.steps,
          { id: newId(), tool_name: event.tool_name, tool_input: event.tool_input, state: "running", duration_ms: null, diagnostics: null },
        ],
      };
    case "tool_end": {
      const index = turn.steps.findIndex((s) => s.state === "running" && s.tool_name === event.tool_name);
      const finished: ToolStep = {
        id: index >= 0 ? turn.steps[index]!.id : newId(),
        tool_name: event.tool_name,
        tool_input: index >= 0 ? turn.steps[index]!.tool_input : null,
        state: "done",
        duration_ms: event.duration_ms,
        diagnostics: event.diagnostics,
      };
      // The live backend emits only tool_end, so a step may appear already finished.
      const steps = index >= 0 ? turn.steps.map((s, i) => (i === index ? finished : s)) : [...turn.steps, finished];
      return { ...turn, steps, diagnostics: event.diagnostics ?? turn.diagnostics };
    }
    case "token":
      return { ...turn, answer: turn.answer + event.content };
    case "metadata":
      return {
        ...turn,
        status: "done",
        citations: event.citations,
        diagnostics: event.diagnostics ?? turn.diagnostics,
        duration_ms: event.duration_ms,
        message_id: event.message_id ?? turn.message_id,
      };
  }
}

function turnsFromHistory(messages: readonly ChatMessageResponse[], params: Turn["params"]): Turn[] {
  const turns: Turn[] = [];
  for (const message of messages) {
    if (message.role === "user") {
      turns.push({
        id: message.id,
        question: message.content,
        answer: "",
        status: "done",
        steps: [],
        citations: [],
        diagnostics: null,
        duration_ms: null,
        source: "fastapi",
        created_at: message.created_at,
        params,
        message_id: null,
        feedback: null,
        evidence: {},
      });
      continue;
    }
    const last = turns.at(-1);
    if (!last || last.answer) continue;
    const tools = (message.executed_tools ?? []) as Array<{ tool_name?: string; duration_ms?: number | null; diagnostics?: SearchDiagnostics | null }>;
    turns[turns.length - 1] = {
      ...last,
      answer: message.content,
      message_id: message.id,
      citations: (message.citations ?? []) as unknown as CitationItem[],
      steps: tools.map((t) => ({
        id: newId(),
        tool_name: t.tool_name ?? "tool",
        tool_input: null,
        state: "done",
        duration_ms: t.duration_ms ?? null,
        diagnostics: t.diagnostics ?? null,
      })),
      diagnostics: [...tools].reverse().find((t) => t.diagnostics)?.diagnostics ?? null,
    };
  }
  return turns;
}

export function useAgentChat() {
  const [session, setSession] = useState<ChatSession>(EMPTY_SESSION);
  const [localSessions, setLocalSessions] = useState<Record<string, ChatSession>>({});
  const controller = useRef<AbortController | null>(null);
  const busy = session.turns.some((t) => t.status === "streaming");

  // Leaving the page cancels the in-flight stream (and, through the BFF, the upstream FastAPI turn).
  useEffect(() => () => controller.current?.abort(), []);

  const updateTurn = useCallback((id: string, update: (turn: Turn) => Turn) => {
    setSession((s) => ({ ...s, turns: s.turns.map((t) => (t.id === id ? update(t) : t)) }));
  }, []);

  /** Re-runs the turn's search once through /api/search to show RRF scores, content and parent blocks. */
  const hydrateEvidence = useCallback(
    async (turn: Turn, query: string) => {
      try {
        const result = await api.search({
          query,
          top_k: turn.params.top_k,
          mode: turn.params.search_mode,
          rerank: turn.params.enable_rerank,
          filter_document_id: turn.params.filter_document_id,
        });
        const evidence: Record<string, SearchResultItem> = Object.fromEntries(result.results.map((r) => [r.chunk_id, r]));
        updateTurn(turn.id, (t) => ({ ...t, evidence }));
      } catch {
        // evidence is an enhancement: citations still render without it
      }
    },
    [updateTurn],
  );

  const send = useCallback(
    async (message: string, params: Hyperparameters, filterDocumentId: string | null) => {
      const text = message.trim();
      if (!text || busy) return;
      const turn: Turn = {
        id: newId(),
        question: text,
        answer: "",
        status: "streaming",
        steps: [],
        citations: [],
        diagnostics: null,
        duration_ms: null,
        source: null,
        created_at: new Date().toISOString(),
        params: { ...params, filter_document_id: filterDocumentId },
        message_id: null,
        feedback: null,
        evidence: {},
      };
      setSession((s) => ({ ...s, title: s.turns.length ? s.title : text.slice(0, 80), turns: [...s.turns, turn] }));
      controller.current = new AbortController();
      let current = turn;
      let sessionId: string | null = session.id;
      try {
        const { response, source } = await api.chatStream(
          { message: text, session_id: session.id, filter_document_id: filterDocumentId, ...params },
          controller.current.signal,
        );
        current = { ...current, source };
        updateTurn(turn.id, (t) => ({ ...t, source }));
        for await (const event of readAgentStream(response, controller.current.signal)) {
          current = applyEvent(current, event);
          if (event.type === "metadata") sessionId = event.session_id;
          const snapshot = current;
          updateTurn(turn.id, () => snapshot);
        }
        if (current.status === "streaming") current = { ...current, status: "done" };
        const finished = current;
        updateTurn(turn.id, () => finished);
        if (sessionId) {
          const id = sessionId;
          // The user may have switched sessions while streaming: only adopt the id if this turn is still shown.
          setSession((s) => (s.turns.some((t) => t.id === turn.id) ? { ...s, id } : s));
          const searchStep = finished.steps.find((s) => s.tool_name === "search_knowledge_base");
          const query = typeof searchStep?.tool_input?.query === "string" ? searchStep.tool_input.query : text;
          void hydrateEvidence(finished, query);
          if (!finished.message_id) {
            // Fallback for backends whose metadata event predates `message_id`.
            const history = await api.history(id).catch(() => null);
            const lastAssistant = history?.messages.filter((m) => m.role === "assistant").at(-1);
            if (lastAssistant) updateTurn(turn.id, (t) => ({ ...t, message_id: lastAssistant.id }));
          }
        }
      } catch (error) {
        const aborted = error instanceof DOMException && error.name === "AbortError";
        updateTurn(turn.id, (t) => ({
          ...t,
          status: aborted ? "done" : "error",
          error: aborted ? undefined : error instanceof Error ? error.message : "The agent stream failed.",
        }));
      } finally {
        controller.current = null;
      }
    },
    [busy, hydrateEvidence, session.id, updateTurn],
  );

  const stop = useCallback(() => controller.current?.abort(), []);

  const remember = useCallback((s: ChatSession) => {
    if (s.id && s.turns.length) setLocalSessions((all) => ({ ...all, [s.id as string]: s }));
  }, []);

  const reset = useCallback(() => {
    remember(session);
    setSession(EMPTY_SESSION);
  }, [remember, session]);

  const open = useCallback(
    async (id: string, params: Turn["params"]) => {
      remember(session);
      const local = localSessions[id];
      if (local) {
        setSession(local);
        return;
      }
      const history = await api.history(id);
      setSession({ id, title: history.messages[0]?.content.slice(0, 80) ?? "Session", turns: turnsFromHistory(history.messages, params) });
    },
    [localSessions, remember, session],
  );

  const forget = useCallback(
    (id: string) => {
      setLocalSessions((all) => Object.fromEntries(Object.entries(all).filter(([key]) => key !== id)));
      if (session.id === id) setSession(EMPTY_SESSION);
    },
    [session.id],
  );

  const rate = useCallback(
    async (turn: Turn, rating: 1 | -1) => {
      if (!session.id || !turn.message_id) return;
      await api.feedback(session.id, turn.message_id, rating);
      updateTurn(turn.id, (t) => ({ ...t, feedback: rating }));
    },
    [session.id, updateTurn],
  );

  return { session, localSessions, busy, send, stop, reset, open, forget, rate, remember };
}
