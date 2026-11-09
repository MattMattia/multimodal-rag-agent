/**
 * Contract surface shared by the BFF, the showcase engine and the UI.
 *
 * Source of truth: the FastAPI OpenAPI document exported to `openapi.json`
 * (`app.openapi()`), compiled into `api-schema.ts` by `npm run contracts:generate`.
 * Only the SSE event union is hand-written, because Server-Sent Events are not described by OpenAPI;
 * it mirrors `AutonomousAgentService.execute_turn_stream` in `app/services/agent.py`.
 */
import type { components } from "./api-schema";

type Schemas = components["schemas"];

/** Makes the listed keys optional: OpenAPI marks fields that have server defaults as required. */
type WithDefaults<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

export type SearchMode = Schemas["SearchRequest"]["mode"];
export type SearchDiagnostics = Schemas["SearchDiagnostics"];
export type SearchRequest = WithDefaults<
  Schemas["SearchRequest"],
  "top_k" | "mode" | "include_parent" | "rerank"
>;
export type SearchResultItem = Schemas["SearchResultItem"];
export type SearchResponse = Schemas["SearchResponse"];

export type AgentChatRequest = WithDefaults<
  Schemas["AgentChatRequest"],
  "search_mode" | "top_k" | "enable_rerank" | "language"
>;
/** Answer language of an agent turn: an explicit locale or "auto" (detect from the question; backend default). */
export type ChatLanguage = NonNullable<AgentChatRequest["language"]>;
/** `lang` query of the export and evaluate endpoints (backend default "es"). */
export type ResponseLanguage = Exclude<ChatLanguage, "auto">;
export type AgentChatResponse = Schemas["AgentChatResponse"];
export type CitationItem = Schemas["CitationItem"];
export type ToolExecutionRecord = Schemas["ToolExecutionRecord"];
export type ChatMessageResponse = Schemas["ChatMessageResponse"];
export type ChatHistoryResponse = Schemas["ChatHistoryResponse"];
export type SessionSummary = Schemas["SessionSummary"];
export type FeedbackRequest = WithDefaults<Schemas["FeedbackRequest"], never>;
export type FeedbackResponse = Schemas["FeedbackResponse"];

export type DocumentResponse = Schemas["DocumentResponse"];
export type DocumentDetailResponse = Schemas["DocumentDetailResponse"];
export type DocumentChunkResponse = Schemas["DocumentChunkResponse"];
export type DocumentImageResponse = Schemas["DocumentImageResponse"];
export type DocumentUploadResponse = Schemas["DocumentUploadResponse"];

export type DemoSeedResponse = Schemas["DemoSeedResponse"];
export type DemoStatusResponse = Schemas["DemoStatusResponse"];
export type EvaluateRequest = WithDefaults<Schemas["EvaluateRequest"], "top_k">;
export type EvaluationResponse = Schemas["EvaluationResponse"];
export type ModeEvaluation = Schemas["ModeEvaluation"];
export type QueryEvaluation = Schemas["QueryEvaluation"];
export type EvaluationModeName = "dense" | "sparse" | "hybrid";

/** Which engine answered a BFF request (also sent as the `x-rag-source` response header). */
export type DataSource = "fastapi" | "showcase";
export const SOURCE_HEADER = "x-rag-source";

/**
 * `/api/demo/status` as returned by the BFF: the backend `DemoStatusResponse` plus `source`.
 * The showcase engine has no database, so it reports `db_dialect: "in-memory"` (BFF-only extension).
 */
export type BffDemoStatus = Omit<DemoStatusResponse, "db_dialect"> & {
  db_dialect: DemoStatusResponse["db_dialect"] | "in-memory";
  source: DataSource;
};

// --- SSE events of POST /agent/chat/stream -----------------------------------------------------------
/** Emitted before each tool runs (live backend and showcase engine). */
export interface ToolStartEvent {
  type: "tool_start";
  tool_name: string;
  tool_input: Record<string, unknown>;
}

export interface ToolEndEvent {
  type: "tool_end";
  tool_name: string;
  duration_ms: number | null;
  diagnostics: SearchDiagnostics | null;
}

export interface TokenEvent {
  type: "token";
  content: string;
}

export interface MetadataEvent {
  type: "metadata";
  citations: CitationItem[];
  executed_tools: ToolExecutionRecord[];
  session_id: string;
  /**
   * Id of the persisted assistant message, used for feedback. `null` when the backend could not persist it;
   * absent on backends that predate it.
   */
  message_id?: string | null;
  diagnostics: SearchDiagnostics | null;
  duration_ms: number;
}

export type AgentStreamEvent = ToolStartEvent | ToolEndEvent | TokenEvent | MetadataEvent;

/** Body accepted by the BFF export route; the transcript is only used by the showcase fallback. */
export interface ExportTranscriptMessage {
  role: "user" | "assistant";
  content: string;
  created_at: string;
  citations?: CitationItem[];
  executed_tools?: Array<Pick<ToolExecutionRecord, "tool_name">>;
}

export type ExportFormat = "markdown" | "pdf";
