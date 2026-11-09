// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import type { EvaluationResponse } from "@/lib/contracts";
import { en } from "@/lib/i18n/en";
import { es } from "@/lib/i18n/es";
import { LocaleProvider } from "@/lib/i18n/LocaleProvider";
import { LOCALE_STORAGE_KEY, type Locale } from "@/lib/i18n/types";
import { AgentStudio } from "./agent/AgentStudio";
import { AdrViewer } from "./architecture/AdrViewer";
import { BenchmarkLab } from "./benchmark/BenchmarkLab";
import { KnowledgeBase } from "./knowledge/KnowledgeBase";
import { NavTabs } from "./shell/NavTabs";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

const DICTS = { es, en } as const;
const LOCALES: Locale[] = ["es", "en"];

function renderIn(locale: Locale, ui: ReactNode) {
  localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

const json = (data: unknown) => new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });

const sse = (events: unknown[]) =>
  new Response(events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join(""), {
    status: 200,
    headers: { "Content-Type": "text/event-stream", "x-rag-source": "showcase" },
  });

const EVALUATION: EvaluationResponse = {
  top_k: 5,
  num_queries: 1,
  embedding_mode: "mock",
  warnings: [],
  modes: {
    hybrid: {
      semantic: false,
      hit_rate_at_k: 1,
      mrr: 1,
      ndcg_at_k: 1,
      avg_latency_ms: 2,
      per_query: [
        { id: "q1", query: "HNSW", category: "exact", hit: true, reciprocal_rank: 1, ndcg: 1, latency_ms: 2, relevances: [1], top_documents: [] },
      ],
    },
  },
};

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (input) => {
    const url = String(input);
    if (url.startsWith("/api/chat/stream")) {
      return sse([
        { type: "tool_start", tool_name: "search_knowledge_base", tool_input: { query: "x" } },
        { type: "tool_end", tool_name: "search_knowledge_base", duration_ms: 1, diagnostics: null },
        { type: "token", content: "ok" },
        { type: "metadata", citations: [], executed_tools: [], session_id: "6a1c7f80-1e5b-4a0c-9d55-3b8f2d9e4c11", message_id: "7b2d8e91-2f6c-4b1d-8e66-4c9a3eaf5d22", diagnostics: null, duration_ms: 3 },
      ]);
    }
    if (url.startsWith("/api/demo/evaluate")) return json(EVALUATION);
    if (url.startsWith("/api/search")) return json({ query: "x", total_results: 0, results: [] });
    return json([]);
  });
  vi.stubGlobal("fetch", fetchMock);
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const bodyOf = (url: string) => {
  const call = fetchMock.mock.calls.find(([input]) => String(input).startsWith(url));
  return call ? (JSON.parse(String(call[1]?.body)) as Record<string, unknown>) : null;
};

describe.each(LOCALES)("views in %s", (locale) => {
  const t = DICTS[locale];

  it("NavTabs renders the localized view names", () => {
    renderIn(locale, <NavTabs />);
    const nav = screen.getByRole("navigation", { name: t.shell.navLabel });
    expect(nav).toHaveTextContent(t.shell.nav.knowledge);
    expect(nav).toHaveTextContent(t.shell.nav.benchmark);
    expect(nav).toHaveTextContent(t.shell.nav.architecture);
    expect(screen.getByRole("link", { name: t.shell.nav.agent })).toHaveAttribute("aria-current", "page");
  });

  it("AgentStudio renders localized texts and sends the quick prompt in the active language", async () => {
    const user = userEvent.setup();
    renderIn(locale, <AgentStudio />);
    expect(screen.getByRole("heading", { name: t.agent.emptyTitle })).toBeInTheDocument();
    expect(screen.getByPlaceholderText(t.agent.placeholder)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t.agent.send })).toBeInTheDocument();
    expect(screen.getByText(t.agent.sidebar.empty)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: t.agent.params.title })).toBeInTheDocument();

    const prompt = t.agent.quickPrompts[0]!;
    await user.click(screen.getByRole("button", { name: prompt }));
    await waitFor(() => expect(bodyOf("/api/chat/stream")).not.toBeNull());
    expect(bodyOf("/api/chat/stream")).toMatchObject({ message: prompt, language: locale });
    expect(await screen.findByText(t.agent.turn.sourceShowcase)).toBeInTheDocument();
  });

  it("KnowledgeBase renders localized texts", async () => {
    renderIn(locale, <KnowledgeBase />);
    expect(screen.getByRole("heading", { level: 1, name: t.knowledge.title })).toBeInTheDocument();
    expect(screen.getByText(t.knowledge.dropHint)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: new RegExp(t.knowledge.restore) })).toBeInTheDocument();
    expect(await screen.findByText(t.knowledge.selectDocument)).toBeInTheDocument();
    expect(screen.getByText(t.knowledge.noImages)).toBeInTheDocument();
  });

  it("BenchmarkLab renders localized texts and requests the evaluation in the active language", async () => {
    const user = userEvent.setup();
    renderIn(locale, <BenchmarkLab />);
    expect(screen.getByRole("heading", { level: 1, name: t.benchmark.title })).toBeInTheDocument();
    expect(screen.getByText(t.benchmark.empty)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: new RegExp(t.benchmark.run) }));
    expect(await screen.findByText(t.benchmark.perQueryTitle)).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: t.benchmark.columns.query })).toBeInTheDocument();
    expect(screen.getByText(t.benchmark.avgLatency)).toBeInTheDocument();
    expect(screen.getByText("Hit Rate@5")).toBeInTheDocument();
    expect(screen.getByText(t.benchmark.queries(1))).toBeInTheDocument();
    const [url] = fetchMock.mock.calls.find(([input]) => String(input).startsWith("/api/demo/evaluate"))!;
    expect(String(url)).toBe(`/api/demo/evaluate?lang=${locale}`);
  });

  it("AdrViewer shows the ADR content of the active language", () => {
    renderIn(
      locale,
      <AdrViewer
        adrs={[
          {
            slug: "001-chunking",
            en: { title: "ADR 001 — Parent-child chunking", content: "# ADR 001 — Parent-child chunking\n\nEnglish body." },
            es: { title: "ADR 001 — Chunking padre-hijo", content: "# ADR 001 — Chunking padre-hijo\n\nCuerpo en español." },
          },
        ]}
      />,
    );
    expect(screen.getByRole("heading", { name: t.architecture.adr.title })).toBeInTheDocument();
    const body = locale === "es" ? "Cuerpo en español." : "English body.";
    const other = locale === "es" ? "English body." : "Cuerpo en español.";
    expect(screen.getByText(body)).toBeInTheDocument();
    expect(screen.queryByText(other)).not.toBeInTheDocument();
    expect(screen.getByRole("tab")).toHaveTextContent(locale === "es" ? "Chunking padre-hijo" : "Parent-child chunking");
  });
});
