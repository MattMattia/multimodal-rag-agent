"use client";

import { createContext, type ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { BffDemoStatus } from "@/lib/contracts";
import { api } from "@/lib/client/api";

const POLL_MS = 30_000;

interface StatusState {
  status: BffDemoStatus | null;
  error: string | null;
  refresh: () => Promise<void>;
}

const StatusContext = createContext<StatusState>({ status: null, error: null, refresh: async () => {} });

/** Polls `/api/demo/status` and shares which engine (live FastAPI or showcase) is answering. */
export function StatusProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<BffDemoStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const inFlight = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;
    try {
      const next = await api.status(controller.signal);
      setStatus(next);
      setError(null);
    } catch (e) {
      if (controller.signal.aborted) return;
      setError(e instanceof Error ? e.message : "Status unavailable");
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => {
      clearInterval(timer);
      inFlight.current?.abort();
    };
  }, [refresh]);

  return <StatusContext.Provider value={{ status, error, refresh }}>{children}</StatusContext.Provider>;
}

export function useDemoStatus(): StatusState {
  return useContext(StatusContext);
}
