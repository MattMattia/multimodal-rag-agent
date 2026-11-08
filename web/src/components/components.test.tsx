// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { BffDemoStatus, SearchDiagnostics } from "@/lib/contracts";
import { SseParser } from "@/lib/client/sse";
import { CitationCard } from "./agent/CitationCard";
import { LatencyXRay } from "./agent/LatencyXRay";
import { applyEvent } from "./agent/useAgentChat";
import { DEFAULT_HYPERPARAMETERS, type Turn } from "./agent/types";
import { LIVE_LABEL, SHOWCASE_LABEL, StatusBadgeView } from "./shell/StatusBadge";
import { Markdown } from "./Markdown";

const diagnostics: SearchDiagnostics = {
  db_dialect: "postgresql",
  embedding_ms: 38,
  dense_ms: 6,
  sparse_ms: 4,
  rrf_fusion_ms: 1,
  rerank_ms: 120,
  total_ms: 175,
  raw_candidates_count: 20,
  deduped_blocks_count: 8,
};

const status = (source: "fastapi" | "showcase"): BffDemoStatus => ({
  source,
  db_dialect: source === "fastapi" ? "sqlite" : "in-memory",
  demo_seeded: true,
  total_documents: 3,
  total_chunks: 34,
  total_images: 3,
  gemini_configured: false,
  langfuse_enabled: false,
  active_models: {},
  embedding_mode: "mock",
});

describe("StatusBadgeView", () => {
  it("shows the live cluster label with the database dialect", () => {
    render(<StatusBadgeView status={status("fastapi")} error={null} />);
    expect(screen.getByText(LIVE_LABEL)).toBeInTheDocument();
    expect(screen.getByText("db: sqlite")).toBeInTheDocument();
  });

  it("shows the serverless showcase label without a dialect badge", () => {
    render(<StatusBadgeView status={status("showcase")} error={null} />);
    expect(screen.getByRole("status")).toHaveTextContent(SHOWCASE_LABEL);
    expect(screen.queryByText(/^db:/)).not.toBeInTheDocument();
  });
});

describe("LatencyXRay", () => {
  it("lists every pipeline stage in milliseconds with an accessible summary", () => {
    render(<LatencyXRay diagnostics={diagnostics} />);
    const region = screen.getByRole("region", { name: "Latency X-ray" });
    expect(within(region).getByRole("img")).toHaveAccessibleName(/Semantic rerank 120 ms/);
    expect(within(region).getByText("total 175 ms")).toBeInTheDocument();
    expect(within(region).getByText(/Candidates 20 → 8 parent blocks/)).toBeInTheDocument();
  });
});

describe("Markdown", () => {
  it("renders tables and routes backend report links through the BFF", () => {
    render(<Markdown source={"See [report](/uploads/reports/reporte_1_x.pdf).\n\n| Region | Revenue |\n| --- | --- |\n| EMEA | $28M |"} />);
    expect(screen.getByRole("link", { name: "report" })).toHaveAttribute("href", "/api/reports/reporte_1_x.pdf");
    expect(screen.getByRole("columnheader", { name: "Region" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "$28M" })).toBeInTheDocument();
  });

  it("keeps snake_case file names intact while supporting _italic_ words", () => {
    const { container } = render(<Markdown source={"Source [Reporte_Financiero_Q3_GlobalTech.pdf, p. 2] and _note_."} />);
    expect(container).toHaveTextContent("Reporte_Financiero_Q3_GlobalTech.pdf");
    expect(container.querySelectorAll("em")).toHaveLength(1);
  });

  it("does not render unsafe link targets", () => {
    render(<Markdown source={"[click](javascript:alert(1))"} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText(/click/)).toBeInTheDocument();
  });
});

describe("CitationCard", () => {
  it("shows RRF and rerank badges and toggles the table viewer", async () => {
    const user = userEvent.setup();
    render(
      <CitationCard
        citation={{ document_name: "Reporte_Financiero_Q3_GlobalTech.pdf", page_number: 2, chunk_type: "table", chunk_id: "c1", rerank_score: 0.91 }}
        evidence={{
          chunk_id: "c1",
          document_id: "d1",
          document_name: "Reporte_Financiero_Q3_GlobalTech.pdf",
          content: "| Región | Ingresos |\n| --- | --- |\n| LATAM | $19M |",
          chunk_type: "table",
          score: 0.032787,
          rank: 1,
        }}
      />,
    );
    expect(screen.getByText("RRF 0.0328")).toBeInTheDocument();
    expect(screen.getByText("Rerank 0.91")).toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: "View table" });
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("cell", { name: "$19M" })).toBeInTheDocument();
  });
});

describe("agent stream client", () => {
  it("parses SSE frames split across chunks", () => {
    const parser = new SseParser();
    expect(parser.feed('data: {"type":"tok')).toEqual([]);
    expect(parser.feed('en","content":"Hi"}\n\ndata: {"type":"token","content":"!"}\n\n')).toEqual([
      { type: "token", content: "Hi" },
      { type: "token", content: "!" },
    ]);
    expect(parser.feed("data: not-json\n\n")).toEqual([]);
  });

  it("builds a turn from tool_start/tool_end/token/metadata, including live streams without tool_start", () => {
    let turn: Turn = {
      id: "t",
      question: "q",
      answer: "",
      status: "streaming",
      steps: [],
      citations: [],
      diagnostics: null,
      duration_ms: null,
      source: "fastapi",
      created_at: "2026-01-01T00:00:00Z",
      params: { ...DEFAULT_HYPERPARAMETERS, filter_document_id: null },
      message_id: null,
      feedback: null,
      evidence: {},
    };
    turn = applyEvent(turn, { type: "tool_start", tool_name: "search_knowledge_base", tool_input: { query: "q" } });
    expect(turn.steps[0]).toMatchObject({ state: "running" });
    turn = applyEvent(turn, { type: "tool_end", tool_name: "search_knowledge_base", duration_ms: 12.5, diagnostics });
    turn = applyEvent(turn, { type: "tool_end", tool_name: "generate_report_pdf", duration_ms: 3, diagnostics: null });
    expect(turn.steps.map((s) => [s.tool_name, s.state, s.duration_ms])).toEqual([
      ["search_knowledge_base", "done", 12.5],
      ["generate_report_pdf", "done", 3],
    ]);
    turn = applyEvent(turn, { type: "token", content: "Hello " });
    turn = applyEvent(turn, { type: "token", content: "world" });
    turn = applyEvent(turn, { type: "metadata", citations: [], executed_tools: [], session_id: "s", message_id: "m-1", diagnostics, duration_ms: 99 });
    expect(turn).toMatchObject({ answer: "Hello world", status: "done", duration_ms: 99, diagnostics, message_id: "m-1" });
  });
});
