/** Browser-side client for the BFF (`/api/*`). It never talks to FastAPI directly. */
import type {
  AgentChatRequest,
  BffDemoStatus,
  ChatHistoryResponse,
  DataSource,
  DemoSeedResponse,
  DocumentDetailResponse,
  DocumentResponse,
  DocumentUploadResponse,
  EvaluationResponse,
  ExportFormat,
  ExportTranscriptMessage,
  FeedbackResponse,
  ResponseLanguage,
  SearchRequest,
  SearchResponse,
  SessionSummary,
} from "../contracts";
import { SOURCE_HEADER } from "../contracts";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function errorFrom(response: Response): Promise<ApiError> {
  let detail = `${response.status} ${response.statusText}`.trim();
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail)) detail = body.detail.map((d) => (d as { msg?: string }).msg ?? "").join("; ");
  } catch {
    // non-JSON error body: keep the status text
  }
  return new ApiError(response.status, detail);
}

async function json<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, { cache: "no-store", ...init });
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as T;
}

const post = (body?: unknown, signal?: AbortSignal): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
  signal,
});

export const api = {
  status: (signal?: AbortSignal) => json<BffDemoStatus>("/api/demo/status", { signal }),
  seed: () => json<DemoSeedResponse>("/api/demo/seed", post()),
  /** `lang` localizes the benchmark warnings (live backend and showcase engine). */
  evaluate: (topK: number, lang: ResponseLanguage, signal?: AbortSignal) =>
    json<EvaluationResponse>(`/api/demo/evaluate?lang=${lang}`, post({ top_k: topK }, signal)),
  search: (request: SearchRequest, signal?: AbortSignal) => json<SearchResponse>("/api/search", post(request, signal)),
  documents: (signal?: AbortSignal) => json<DocumentResponse[]>("/api/documents", { signal }),
  document: (id: string, signal?: AbortSignal) => json<DocumentDetailResponse>(`/api/documents/${id}`, { signal }),
  sessions: (signal?: AbortSignal) => json<SessionSummary[]>("/api/sessions", { signal }),
  history: (id: string) => json<ChatHistoryResponse>(`/api/sessions/${id}/history`),
  deleteSession: async (id: string): Promise<void> => {
    const response = await fetch(`/api/sessions/${id}`, { method: "DELETE" });
    if (!response.ok && response.status !== 404) throw await errorFrom(response);
  },
  feedback: (sessionId: string, messageId: string, rating: 1 | -1) =>
    json<FeedbackResponse>("/api/feedback", post({ session_id: sessionId, message_id: messageId, rating })),
  upload: async (file: File): Promise<DocumentUploadResponse> => {
    const form = new FormData();
    form.append("file", file);
    return json<DocumentUploadResponse>("/api/documents", { method: "POST", body: form });
  },
  exportSession: async (
    id: string,
    format: ExportFormat,
    messages: readonly ExportTranscriptMessage[],
    lang: ResponseLanguage,
  ): Promise<{ blob: Blob; filename: string }> => {
    const response = await fetch(`/api/sessions/${id}/export?format=${format}&lang=${lang}`, post({ messages }));
    if (!response.ok) throw await errorFrom(response);
    const disposition = response.headers.get("content-disposition") ?? "";
    const filename = /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? `session-${id}.${format === "pdf" ? "pdf" : "md"}`;
    return { blob: await response.blob(), filename };
  },
  chatStream: async (request: AgentChatRequest, signal: AbortSignal): Promise<{ response: Response; source: DataSource }> => {
    const response = await fetch("/api/chat/stream", post(request, signal));
    if (!response.ok) throw await errorFrom(response);
    return { response, source: (response.headers.get(SOURCE_HEADER) as DataSource | null) ?? "fastapi" };
  },
};

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Backend answers may link reports as /uploads/reports/x.pdf or /api/v1/reports/x.pdf; route them via the BFF. */
export function toBffHref(href: string): string {
  const report = /^(?:https?:\/\/[^/]+)?\/(?:uploads|api\/v1)\/reports\/([A-Za-z0-9._-]+\.pdf)$/.exec(href);
  return report ? `/api/reports/${report[1]}` : href;
}
