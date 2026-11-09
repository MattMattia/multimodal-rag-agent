/**
 * Serverless ReAct turn for the showcase: a deterministic, extractive stand-in for the Gemini agent.
 * It runs the real retrieval pipeline as a `search_knowledge_base` tool call, optionally a
 * `generate_report_pdf` tool call, then streams an answer built from the retrieved evidence.
 * No language model is involved; the answer only quotes the Golden Corpus.
 */
import type {
  AgentChatRequest,
  AgentStreamEvent,
  CitationItem,
  SearchResponse,
  SearchResultItem,
  ToolExecutionRecord,
} from "../contracts";
import { SHOWCASE_DEFAULT_LOCALE, SHOWCASE_TEXT, type ShowcaseLocale, resolveLocale } from "./i18n";
import { tokenize } from "./lexical";
import { reportFilenameFor } from "./reports";
import { assertSearchableDocument, searchCorpus } from "./search";

const REPORT_INTENT = /\b(pdf|report|reporte|informe|descargar)\b/i;
const SENTENCE_SPLIT = /(?<=[.!?])\s+|\n+/;
const DEFAULT_TOP_K = 5;
const DEFAULT_MAX_TURNS = 5;

export function encodeSse(event: AgentStreamEvent): string {
  return `data: ${JSON.stringify(event)}\n\n`;
}

/** The sentence of a result (or its parent block) that shares the most terms with the question. */
function bestSentence(question: string, item: SearchResultItem): string {
  const queryTerms = new Set(tokenize(question));
  const source = item.chunk_type === "table" ? item.content : (item.parent_content ?? item.content);
  const sentences = source
    .split(SENTENCE_SPLIT)
    .map((s) => s.replace(/^#+\s*/, "").replace(/^Descripción del gráfico:\s*/, "").trim())
    // Headings, file names and table rows are not answer sentences.
    .filter((s) => s.length >= 40 && !s.startsWith("|") && !s.startsWith("[") && !/^Archivo:/.test(s));
  if (item.chunk_type === "table") {
    const rows = source.split("\n").filter((l) => l.startsWith("|") && !l.includes("---"));
    const matching = rows.filter((r) => tokenize(r).some((t) => queryTerms.has(t)));
    const cells = (row: string): string =>
      row
        .split("|")
        .map((c) => c.trim())
        .filter(Boolean)
        .join(" · ");
    return (matching.length ? matching : rows.slice(1)).slice(0, 3).map(cells).join("; ");
  }
  let best = sentences[0] ?? source.slice(0, 220);
  let bestScore = -1;
  for (const sentence of sentences) {
    const score = tokenize(sentence).filter((t) => queryTerms.has(t)).length;
    if (score > bestScore) {
      best = sentence;
      bestScore = score;
    }
  }
  return best.length > 320 ? `${best.slice(0, 317)}...` : best;
}

function citationLabel(item: SearchResultItem): string {
  return item.page_number ? `[${item.document_name}, p. ${item.page_number}]` : `[${item.document_name}]`;
}

export function composeAnswer(
  question: string,
  search: SearchResponse,
  reportFilename: string | null,
  locale: ShowcaseLocale = SHOWCASE_DEFAULT_LOCALE,
): string {
  const text = SHOWCASE_TEXT[locale];
  if (search.results.length === 0) return text.noEvidence;
  const lines = [
    text.intro,
    "",
    ...search.results.slice(0, 3).map((item) => `- ${bestSentence(question, item)} ${citationLabel(item)}`),
  ];
  if (reportFilename) lines.push("", text.reportLink(`/api/reports/${reportFilename}`));
  lines.push("", text.disclaimer);
  return lines.join("\n");
}

function toCitations(results: readonly SearchResultItem[]): CitationItem[] {
  const seen = new Set<string>();
  return results.flatMap((item) => {
    if (seen.has(item.chunk_id)) return [];
    seen.add(item.chunk_id);
    return [
      {
        document_name: item.document_name,
        page_number: item.page_number ?? null,
        chunk_type: item.chunk_type,
        chunk_id: item.chunk_id,
        rerank_score: item.rerank_score ?? null,
      },
    ];
  });
}

/** Splits text into small token-like chunks, keeping whitespace so the stream reassembles exactly. */
export function chunkText(text: string): string[] {
  return text.match(/\S+\s*|\s+/g) ?? [];
}

export interface StreamOptions {
  clock?: () => number;
  /** Id generator for new sessions and messages (injectable for deterministic tests). */
  newId?: () => string;
}

export async function* streamAgentTurn(
  request: AgentChatRequest,
  { clock = () => performance.now(), newId = () => crypto.randomUUID() }: StreamOptions = {},
): AsyncGenerator<AgentStreamEvent> {
  assertSearchableDocument(request.filter_document_id ?? null);
  const turnStarted = clock();
  const sessionId = request.session_id ?? newId();
  const topK = request.top_k ?? DEFAULT_TOP_K;
  const maxTurns = request.max_turns ?? DEFAULT_MAX_TURNS;
  const executed: ToolExecutionRecord[] = [];
  // English when no language is sent (legacy callers); "auto" detects the language of the question.
  const locale = resolveLocale(request.language, request.message);

  const searchInput = {
    query: request.message,
    top_k: topK,
    mode: request.search_mode ?? "hybrid",
    rerank: request.enable_rerank ?? true,
    filter_document_id: request.filter_document_id ?? null,
  };
  yield { type: "tool_start", tool_name: "search_knowledge_base", tool_input: searchInput };
  let started = clock();
  const search = searchCorpus({ ...searchInput, include_parent: true }, clock);
  const searchMs = Number((clock() - started).toFixed(3));
  const diagnostics = search.diagnostics ?? null;
  executed.push({
    tool_name: "search_knowledge_base",
    tool_input: searchInput,
    tool_output: { total_found: search.total_results },
    duration_ms: searchMs,
    diagnostics,
  });
  yield { type: "tool_end", tool_name: "search_knowledge_base", duration_ms: searchMs, diagnostics };

  let reportFilename: string | null = null;
  if (REPORT_INTENT.test(request.message) && maxTurns > 1 && search.results.length > 0) {
    reportFilename = reportFilenameFor(request.message, locale);
    const reportInput = { title: SHOWCASE_TEXT[locale].reportTitle, query: request.message };
    yield { type: "tool_start", tool_name: "generate_report_pdf", tool_input: reportInput };
    started = clock();
    const reportMs = Number((clock() - started).toFixed(3));
    executed.push({
      tool_name: "generate_report_pdf",
      tool_input: reportInput,
      tool_output: { status: "success", filename: reportFilename, download_url: `/api/reports/${reportFilename}` },
      duration_ms: reportMs,
      diagnostics: null,
    });
    yield { type: "tool_end", tool_name: "generate_report_pdf", duration_ms: reportMs, diagnostics: null };
  }

  for (const content of chunkText(composeAnswer(request.message, search, reportFilename, locale))) {
    yield { type: "token", content };
  }

  yield {
    type: "metadata",
    citations: toCitations(search.results),
    executed_tools: executed,
    session_id: sessionId,
    // Not persisted (serverless keeps no state), but lets the UI send feedback exactly like the live flow.
    message_id: newId(),
    diagnostics,
    duration_ms: Number((clock() - turnStarted).toFixed(3)),
  };
}
