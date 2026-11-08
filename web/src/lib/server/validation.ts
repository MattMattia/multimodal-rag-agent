/**
 * Boundary validation for BFF inputs, mirroring the Pydantic constraints in `app/schemas/*.py`.
 * Route params are validated before anything is proxied, so user input never reshapes backend paths.
 */
import type {
  AgentChatRequest,
  EvaluateRequest,
  ExportFormat,
  ExportTranscriptMessage,
  FeedbackRequest,
  SearchMode,
  SearchRequest,
} from "../contracts";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** Same rule as the backend report names (`reporte_<id>_<slug>.pdf`) and showcase report names. */
const REPORT_FILENAME_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,250}\.pdf$/;
const SEARCH_MODES: readonly SearchMode[] = ["hybrid", "dense", "sparse"];
export const MAX_MESSAGE_CHARS = 8000;
const MAX_EXPORT_MESSAGES = 200;

export type Validated<T> = { ok: true; value: T } | { ok: false; error: string };

const ok = <T>(value: T): Validated<T> => ({ ok: true, value });
const fail = <T>(error: string): Validated<T> => ({ ok: false, error });

export function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID_RE.test(value);
}

export function isReportFilename(value: string): boolean {
  return REPORT_FILENAME_RE.test(value) && !value.includes("..");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalUuid(body: Record<string, unknown>, key: string): Validated<string | null> {
  const value = body[key];
  if (value === undefined || value === null || value === "") return ok(null);
  return isUuid(value) ? ok(value) : fail(`${key} must be a UUID`);
}

function intInRange(body: Record<string, unknown>, key: string, min: number, max: number, fallback: number): Validated<number> {
  const value = body[key] ?? fallback;
  return typeof value === "number" && Number.isInteger(value) && value >= min && value <= max
    ? ok(value)
    : fail(`${key} must be an integer between ${min} and ${max}`);
}

function bool(body: Record<string, unknown>, key: string, fallback: boolean): Validated<boolean> {
  const value = body[key] ?? fallback;
  return typeof value === "boolean" ? ok(value) : fail(`${key} must be a boolean`);
}

function text(body: Record<string, unknown>, key: string): Validated<string> {
  const value = body[key];
  if (typeof value !== "string" || !value.trim()) return fail(`${key} must be a non-empty string`);
  return value.length > MAX_MESSAGE_CHARS ? fail(`${key} must be at most ${MAX_MESSAGE_CHARS} characters`) : ok(value);
}

function mode(body: Record<string, unknown>, key: string): Validated<SearchMode> {
  const value = body[key] ?? "hybrid";
  return SEARCH_MODES.includes(value as SearchMode) ? ok(value as SearchMode) : fail(`${key} must be hybrid, dense or sparse`);
}

function collect<T>(checks: Record<string, Validated<unknown>>, build: (v: Record<string, unknown>) => T): Validated<T> {
  const values: Record<string, unknown> = {};
  for (const [key, check] of Object.entries(checks)) {
    if (!check.ok) return fail(check.error);
    values[key] = check.value;
  }
  return ok(build(values));
}

export function parseChatRequest(body: unknown): Validated<AgentChatRequest> {
  if (!isRecord(body)) return fail("body must be a JSON object");
  const temperature = body.temperature ?? null;
  if (temperature !== null && (typeof temperature !== "number" || temperature < 0 || temperature > 2)) {
    return fail("temperature must be a number between 0 and 2");
  }
  const maxTurns = body.max_turns === undefined || body.max_turns === null ? ok(null) : intInRange(body, "max_turns", 1, 10, 5);
  return collect(
    {
      message: text(body, "message"),
      session_id: optionalUuid(body, "session_id"),
      filter_document_id: optionalUuid(body, "filter_document_id"),
      search_mode: mode(body, "search_mode"),
      top_k: intInRange(body, "top_k", 1, 50, 5),
      enable_rerank: bool(body, "enable_rerank", true),
      max_turns: maxTurns,
    },
    (v) => ({ ...(v as unknown as AgentChatRequest), temperature: temperature as number | null }),
  );
}

export function parseSearchRequest(body: unknown): Validated<SearchRequest> {
  if (!isRecord(body)) return fail("body must be a JSON object");
  return collect(
    {
      query: text(body, "query"),
      top_k: intInRange(body, "top_k", 1, 50, 5),
      filter_document_id: optionalUuid(body, "filter_document_id"),
      mode: mode(body, "mode"),
      include_parent: bool(body, "include_parent", true),
      rerank: bool(body, "rerank", true),
    },
    (v) => v as unknown as SearchRequest,
  );
}

export function parseEvaluateRequest(body: unknown): Validated<EvaluateRequest> {
  const record = isRecord(body) ? body : {};
  return collect({ top_k: intInRange(record, "top_k", 1, 20, 5) }, (v) => v as unknown as EvaluateRequest);
}

export function parseFeedbackRequest(body: unknown): Validated<FeedbackRequest> {
  if (!isRecord(body)) return fail("body must be a JSON object");
  if (body.rating !== 1 && body.rating !== -1) return fail("rating must be 1 or -1");
  const comment = body.comment ?? null;
  if (comment !== null && (typeof comment !== "string" || comment.length > 2000)) {
    return fail("comment must be a string of at most 2000 characters");
  }
  if (!isUuid(body.session_id) || !isUuid(body.message_id)) return fail("session_id and message_id must be UUIDs");
  return ok({ session_id: body.session_id, message_id: body.message_id, rating: body.rating, comment: comment as string | null });
}

export function parseExportFormat(value: string | null): Validated<ExportFormat> {
  const format = value ?? "markdown";
  return format === "markdown" || format === "pdf" ? ok(format) : fail("format must be markdown or pdf");
}

export function parseTranscript(body: unknown): Validated<ExportTranscriptMessage[]> {
  const messages = isRecord(body) ? body.messages : undefined;
  if (!Array.isArray(messages) || messages.length === 0) return fail("messages must be a non-empty array");
  if (messages.length > MAX_EXPORT_MESSAGES) return fail(`at most ${MAX_EXPORT_MESSAGES} messages can be exported`);
  const parsed: ExportTranscriptMessage[] = [];
  for (const message of messages) {
    if (!isRecord(message) || (message.role !== "user" && message.role !== "assistant")) return fail("invalid message role");
    if (typeof message.content !== "string" || message.content.length > MAX_MESSAGE_CHARS * 4) return fail("invalid message content");
    const citations = Array.isArray(message.citations)
      ? message.citations.filter(isRecord).map((c) => ({
          document_name: String(c.document_name ?? "?"),
          page_number: typeof c.page_number === "number" ? c.page_number : null,
          chunk_type: String(c.chunk_type ?? "text"),
        }))
      : [];
    const tools = Array.isArray(message.executed_tools)
      ? message.executed_tools.filter(isRecord).map((t) => ({ tool_name: String(t.tool_name ?? "?") }))
      : [];
    parsed.push({
      role: message.role,
      content: message.content,
      created_at: typeof message.created_at === "string" ? message.created_at.slice(0, 40) : new Date().toISOString(),
      citations,
      executed_tools: tools,
    });
  }
  return ok(parsed);
}

/** Reads a JSON body; returns `undefined` for an empty or malformed body. */
export async function readJson(request: Request): Promise<unknown> {
  try {
    const raw = await request.text();
    return raw ? (JSON.parse(raw) as unknown) : undefined;
  } catch {
    return undefined;
  }
}
