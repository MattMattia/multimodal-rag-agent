"use client";

import type { BffDemoStatus } from "@/lib/contracts";
import { useDemoStatus } from "./StatusProvider";

export const LIVE_LABEL = "🟢 Live FastAPI + pgvector Cluster";
export const SHOWCASE_LABEL = "⚡ Vercel Serverless 24/7 Showcase Engine";

export function StatusBadgeView({ status, error }: { status: BffDemoStatus | null; error: string | null }) {
  if (!status) {
    return (
      <span className="status-pill" role="status" aria-live="polite">
        {error ? `Status unavailable: ${error}` : "Checking backend…"}
      </span>
    );
  }
  const live = status.source === "fastapi";
  return (
    <span className="row" role="status" aria-live="polite">
      <span className="status-pill" data-source={status.source}>
        {live ? LIVE_LABEL : SHOWCASE_LABEL}
      </span>
      {live && (
        <span className="badge" title="Active database dialect reported by FastAPI">
          db: {status.db_dialect}
        </span>
      )}
    </span>
  );
}

export function StatusBadge() {
  const { status, error } = useDemoStatus();
  return <StatusBadgeView status={status} error={error} />;
}
