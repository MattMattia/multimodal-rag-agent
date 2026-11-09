/**
 * Stateless PDF reports. Serverless functions keep no disk between requests, so a showcase report
 * filename encodes its own question (base64url); `/api/reports/[filename]` re-runs the retrieval and
 * rebuilds the same PDF on every download.
 */
import type { ExportTranscriptMessage, ExportFormat } from "../contracts";
import { SHOWCASE_DEFAULT_LOCALE, SHOWCASE_TEXT, type ShowcaseLocale } from "./i18n";
import { buildPdf } from "./pdf";
import { searchCorpus } from "./search";

export const REPORT_PREFIX = "showcase-report-";
const MAX_QUESTION_BYTES = 120;
/** `showcase-report-<base64url question>[.es].pdf`; no suffix means English (the original format). */
const REPORT_NAME_RE = /^showcase-report-([A-Za-z0-9_-]+)(?:\.(es))?\.pdf$/;

function toBase64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(value: string): Uint8Array | null {
  try {
    const binary = atob(value.replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from(binary, (ch) => ch.charCodeAt(0));
  } catch {
    return null;
  }
}

function truncateUtf8(text: string, maxBytes: number): Uint8Array {
  const encoder = new TextEncoder();
  let result = "";
  for (const ch of text) {
    if (encoder.encode(result + ch).length > maxBytes) break;
    result += ch;
  }
  return encoder.encode(result);
}

/** Spanish reports carry an `.es` suffix so the download rebuilds them in Spanish; legacy names stay English. */
export function reportFilenameFor(question: string, locale: ShowcaseLocale = SHOWCASE_DEFAULT_LOCALE): string {
  const suffix = locale === "es" ? ".es" : "";
  return `${REPORT_PREFIX}${toBase64Url(truncateUtf8(question.trim(), MAX_QUESTION_BYTES))}${suffix}.pdf`;
}

/** The question encoded in a showcase report filename, or null when it is not a showcase report. */
export function decodeReportFilename(filename: string): string | null {
  const match = REPORT_NAME_RE.exec(filename);
  if (!match?.[1]) return null;
  const bytes = fromBase64Url(match[1]);
  if (!bytes) return null;
  try {
    const question = new TextDecoder("utf-8", { fatal: true }).decode(bytes).trim();
    return question || null;
  } catch {
    return null;
  }
}

/** Language of a showcase report filename: "es" with the `.es` suffix, otherwise "en". */
export function decodeReportLocale(filename: string): ShowcaseLocale {
  return REPORT_NAME_RE.exec(filename)?.[2] === "es" ? "es" : "en";
}

export function buildReportPdf(question: string, locale: ShowcaseLocale = SHOWCASE_DEFAULT_LOCALE): Uint8Array {
  const text = SHOWCASE_TEXT[locale];
  const search = searchCorpus({ query: question, top_k: 5, mode: "hybrid", rerank: true });
  const findings = search.results.map((item) => {
    const page = item.page_number ? `, p. ${item.page_number}` : "";
    const scores = `RRF ${item.score.toFixed(4)}${item.rerank_score != null ? ` | rerank ${item.rerank_score.toFixed(2)}` : ""}`;
    return { heading: `${item.rank}. ${item.document_name}${page} (${scores})`, lines: [item.parent_content ?? item.content] };
  });
  const d = search.diagnostics;
  return buildPdf({
    title: text.reportTitle,
    subtitle: text.question(question),
    sections: [
      {
        heading: text.summary,
        lines: [
          text.summaryLine(search.total_results),
          d ? text.xray(d.total_ms, d.dense_ms, d.sparse_ms, d.rrf_fusion_ms, d.rerank_ms) : "",
        ].filter(Boolean),
      },
      ...findings,
    ],
    footer: text.reportFooter,
  });
}

function transcriptMarkdown(sessionId: string, messages: readonly ExportTranscriptMessage[], locale: ShowcaseLocale): string {
  const text = SHOWCASE_TEXT[locale];
  const lines = [`# ${text.conversation(sessionId)}`, ""];
  for (const msg of messages) {
    lines.push(`## ${msg.role === "user" ? text.user : text.agent} (${msg.created_at})`, "", msg.content, "");
    if (msg.citations?.length) {
      lines.push(text.sources);
      for (const c of msg.citations) lines.push(`- ${c.document_name}${c.page_number ? `, p. ${c.page_number}` : ""}`);
      lines.push("");
    }
    if (msg.executed_tools?.length) {
      lines.push(text.tools, ...msg.executed_tools.map((t) => `- \`${t.tool_name}\``), "");
    }
  }
  return lines.join("\n");
}

export interface ExportedFile {
  body: Uint8Array | string;
  contentType: string;
  filename: string;
}

export function exportTranscript(
  sessionId: string,
  messages: readonly ExportTranscriptMessage[],
  format: ExportFormat,
  locale: ShowcaseLocale = SHOWCASE_DEFAULT_LOCALE,
): ExportedFile {
  const text = SHOWCASE_TEXT[locale];
  if (format === "pdf") {
    return {
      body: buildPdf({
        title: text.conversation(sessionId),
        sections: messages.map((m) => ({
          heading: `${m.role === "user" ? text.user : text.agent} - ${m.created_at}`,
          lines: m.content.split(/\n+/).filter(Boolean),
        })),
        footer: text.exportFooter,
      }),
      contentType: "application/pdf",
      filename: `session-${sessionId}.pdf`,
    };
  }
  return {
    body: transcriptMarkdown(sessionId, messages, locale),
    contentType: "text/markdown; charset=utf-8",
    filename: `session-${sessionId}.md`,
  };
}
