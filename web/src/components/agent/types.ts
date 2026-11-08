import type { CitationItem, DataSource, SearchDiagnostics, SearchMode, SearchResultItem } from "@/lib/contracts";

export interface Hyperparameters {
  search_mode: SearchMode;
  top_k: number;
  enable_rerank: boolean;
  temperature: number;
  max_turns: number;
}

export const DEFAULT_HYPERPARAMETERS: Hyperparameters = {
  search_mode: "hybrid",
  top_k: 5,
  enable_rerank: true,
  temperature: 0.2,
  max_turns: 5,
};

export interface ToolStep {
  id: string;
  tool_name: string;
  tool_input: Record<string, unknown> | null;
  state: "running" | "done";
  duration_ms: number | null;
  diagnostics: SearchDiagnostics | null;
}

export interface Turn {
  id: string;
  question: string;
  answer: string;
  status: "streaming" | "done" | "error";
  error?: string;
  steps: ToolStep[];
  citations: CitationItem[];
  diagnostics: SearchDiagnostics | null;
  duration_ms: number | null;
  source: DataSource | null;
  created_at: string;
  params: Hyperparameters & { filter_document_id: string | null };
  /** Backend message id used for feedback (null until known). */
  message_id: string | null;
  feedback: 1 | -1 | null;
  /** Retrieved evidence keyed by chunk id (scores, content, parent block) for the citation cards. */
  evidence: Record<string, SearchResultItem>;
}

export interface ChatSession {
  id: string | null;
  title: string;
  turns: Turn[];
}
