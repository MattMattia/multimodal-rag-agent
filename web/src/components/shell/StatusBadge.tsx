"use client";

import type { BffDemoStatus } from "@/lib/contracts";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import { useDemoStatus } from "./StatusProvider";

export function StatusBadgeView({ status, error }: { status: BffDemoStatus | null; error: string | null }) {
  const { t } = useLocale();
  if (!status) {
    return (
      <span className="status-pill" role="status" aria-live="polite">
        {error ? t.shell.status.unavailable(error) : t.shell.status.checking}
      </span>
    );
  }
  const live = status.source === "fastapi";
  return (
    <span className="row" role="status" aria-live="polite">
      <span className="status-pill" data-source={status.source}>
        {live ? t.shell.status.live : t.shell.status.showcase}
      </span>
      {live && (
        <span className="badge" title={t.shell.status.dialectTitle}>
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
