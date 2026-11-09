import reference from "./__fixtures__/python-reference.json";
import {
  GOLDEN_DOCUMENTS,
  GOLDEN_EVAL_QUERIES,
  allChunks,
  SHOWCASE_EVALUATION_WARNING,
  bm25Scores,
  buildPdf,
  buildReportPdf,
  decodeReportFilename,
  decodeReportLocale,
  encodeSse,
  evaluateCorpus,
  exportTranscript,
  hitRateAtK,
  isRelevant,
  mean,
  ndcgAtK,
  reciprocalRank,
  reportFilenameFor,
  rrfFuse,
  searchCorpus,
  streamAgentTurn,
  tokenize,
} from "../showcase-engine";
import type { AgentStreamEvent } from "../contracts";

const pdfText = (bytes: Uint8Array): string => String.fromCharCode(...bytes);

describe("lexical (port of app/services/lexical.py)", () => {
  it("tokenizes exactly like the Python tokenizer", () => {
    for (const [text, expected] of Object.entries(reference.tokenize_samples)) {
      expect(tokenize(text)).toEqual(expected);
    }
  });

  it("ranks the Golden Corpus with BM25 identically to Python for every golden query", () => {
    const chunks = allChunks();
    const docs = chunks.map((c) => tokenize(c.content));
    for (const ref of reference.bm25_reference) {
      const query = GOLDEN_EVAL_QUERIES.find((q) => q.id === ref.id);
      expect(query).toBeDefined();
      expect(tokenize(query!.query)).toEqual(ref.tokens);
      const scores = bm25Scores(ref.tokens, docs);
      const ranked = chunks
        .map((c, i) => ({ id: c.id, score: scores[i] ?? 0 }))
        .filter((r) => r.score > 0)
        .sort((a, b) => b.score - a.score)
        .slice(0, 10);
      expect(ranked.map((r) => r.id)).toEqual(ref.top.map((r) => r.id));
      ranked.forEach((r, i) => expect(r.score).toBeCloseTo(ref.top[i]!.score, 6));
    }
  });

  it("returns zeros for an empty query or an empty corpus", () => {
    expect(bm25Scores([], [["a"], ["b"]])).toEqual([0, 0]);
    expect(bm25Scores(["a"], [])).toEqual([]);
  });
});

describe("Reciprocal Rank Fusion (k=60)", () => {
  it("sums 1/(k + rank) across rankings with hand-computed values", () => {
    const dense = [{ chunk_id: "a" }, { chunk_id: "b" }, { chunk_id: "c" }];
    const sparse = [{ chunk_id: "c" }, { chunk_id: "a" }];
    const fused = rrfFuse(dense, sparse, 60);
    // a: 1/61 + 1/62 = 0.032522 ; c: 1/63 + 1/61 = 0.032266 ; b: 1/62 = 0.016129
    expect(fused.map((f) => f.chunk_id)).toEqual(["a", "c", "b"]);
    expect(fused[0]!.score).toBeCloseTo(1 / 61 + 1 / 62, 12);
    expect(fused[1]!.score).toBeCloseTo(1 / 63 + 1 / 61, 12);
    expect(fused[2]!.score).toBeCloseTo(1 / 62, 12);
  });

  it("keeps the dense item payload when both rankings contain the chunk and breaks ties by insertion order", () => {
    const fused = rrfFuse([{ chunk_id: "x", tag: "dense" }], [{ chunk_id: "y", tag: "sparse" }, { chunk_id: "x", tag: "sparse" }]);
    expect(fused[0]).toMatchObject({ chunk_id: "x", tag: "dense" });
    const tie = rrfFuse([{ chunk_id: "p" }], [{ chunk_id: "q" }]);
    expect(tie.map((t) => t.chunk_id)).toEqual(["p", "q"]);
  });
});

describe("IR metrics (same cases as tests/test_evaluation.py)", () => {
  it("hit rate @k", () => {
    expect(hitRateAtK([0, 0, 1, 0, 1], 5)).toBe(1);
    expect(hitRateAtK([0, 0, 1, 0, 1], 2)).toBe(0);
    expect(hitRateAtK([0, 0, 0], 3)).toBe(0);
    expect(hitRateAtK([], 3)).toBe(0);
  });

  it("reciprocal rank and MRR", () => {
    expect(reciprocalRank([1, 0, 0])).toBe(1);
    expect(reciprocalRank([0, 0, 1, 1])).toBeCloseTo(1 / 3);
    expect(reciprocalRank([0, 0, 0])).toBe(0);
    expect(reciprocalRank([])).toBe(0);
    expect(reciprocalRank([0, 0, 1], 2)).toBe(0);
    expect(mean([[1, 0], [0, 1], [0, 0]].map((r) => reciprocalRank(r)))).toBeCloseTo(0.5);
    expect(mean([])).toBe(0);
  });

  it("NDCG@k, including the recall-aware variant", () => {
    const expected = (1 / Math.log2(4) + 1 / Math.log2(6)) / (1 / Math.log2(2) + 1 / Math.log2(3));
    expect(expected).toBeCloseTo(0.54377, 4);
    expect(ndcgAtK([0, 0, 1, 0, 1], 5)).toBeCloseTo(expected);
    expect(ndcgAtK([1, 1, 0], 3)).toBe(1);
    expect(ndcgAtK([0, 0, 0], 3)).toBe(0);
    expect(ndcgAtK([], 3)).toBe(0);
    expect(ndcgAtK([0, 1], 1)).toBe(0);
    expect(ndcgAtK([0, 0, 1, 0, 1], 5, 3)).toBeCloseTo(0.41617, 4);
    expect(ndcgAtK([1, 0, 0], 3, 1)).toBe(1);
    expect(ndcgAtK([1, 1], 2, 10)).toBe(1);
    expect(ndcgAtK([1, 0], 2, 2)).toBeCloseTo(1 / (1 + 1 / Math.log2(3)));
    expect(ndcgAtK([0, 0], 2, 0)).toBe(0);
    expect(ndcgAtK([0, 1, 0, 1], 4)).toBeCloseTo(0.6509, 4);
  });

  it("relevance needs the expected document and a keyword in content or parent", () => {
    const result = { document_name: "a.pdf", content: "ingresos", parent_content: "contexto EBITDA 34%" };
    expect(isRelevant(result, ["a.pdf"], ["ebitda"])).toBe(true);
    expect(isRelevant(result, ["b.pdf"], ["ebitda"])).toBe(false);
    expect(isRelevant(result, ["a.pdf"], ["latam"])).toBe(false);
    expect(isRelevant({ document_name: "a.pdf", content: "x", parent_content: null }, ["a.pdf"], [])).toBe(true);
  });
});

describe("Golden Corpus and hybrid search", () => {
  it("embeds the same 3 documents as app/services/demo_corpus.py", () => {
    expect(GOLDEN_DOCUMENTS.map((d) => d.filename)).toEqual([
      "Arquitectura_Cloud_IA_2026.pdf",
      "Reporte_Financiero_Q3_GlobalTech.pdf",
      "Manual_Seguridad_ZeroTrust_OWASP.pdf",
    ]);
    expect(GOLDEN_EVAL_QUERIES).toHaveLength(8);
  });

  it("returns ranked results with parent context and per-stage diagnostics", () => {
    const response = searchCorpus({ query: "¿Cuánto fueron los ingresos de Norteamérica en el trimestre?", top_k: 3 });
    expect(response.mode).toBe("hybrid");
    expect(response.results).toHaveLength(3);
    expect(response.results.map((r) => r.rank)).toEqual([1, 2, 3]);
    expect(response.results[0]!.document_name).toBe("Reporte_Financiero_Q3_GlobalTech.pdf");
    expect(response.results.every((r) => typeof r.rerank_score === "number")).toBe(true);
    const d = response.diagnostics!;
    expect(d.db_dialect).toBe("in-memory");
    expect(d.raw_candidates_count).toBeGreaterThanOrEqual(d.deduped_blocks_count);
    for (const key of ["embedding_ms", "dense_ms", "sparse_ms", "rrf_fusion_ms", "rerank_ms", "total_ms"] as const) {
      expect(d[key]).toBeGreaterThanOrEqual(0);
    }
  });

  it("sparse mode skips the dense stages and rerank=false leaves rerank_score null", () => {
    const response = searchCorpus({ query: "HNSW m=16", mode: "sparse", rerank: false, top_k: 2 });
    expect(response.diagnostics!.dense_ms).toBe(0);
    expect(response.diagnostics!.embedding_ms).toBe(0);
    expect(response.diagnostics!.rerank_ms).toBe(0);
    expect(response.results.every((r) => r.rerank_score === null)).toBe(true);
  });

  it("restricts results to filter_document_id and rejects an unknown document", () => {
    const security = GOLDEN_DOCUMENTS[2]!;
    const response = searchCorpus({ query: "control", filter_document_id: security.id });
    expect(response.results.every((r) => r.document_id === security.id)).toBe(true);
    expect(() => searchCorpus({ query: "x", filter_document_id: "00000000-0000-4000-8000-000000000000" })).toThrow(/does not exist/);
  });
});

describe("RAG benchmark", () => {
  it("evaluates the 8 golden queries in dense, sparse and hybrid with disclosure", () => {
    const report = evaluateCorpus(5);
    expect(report.top_k).toBe(5);
    expect(report.num_queries).toBe(8);
    expect(report.embedding_mode).toBe("mock");
    expect((report.warnings ?? []).some((w) => /not semantic/i.test(w))).toBe(true);
    expect(Object.keys(report.modes).sort()).toEqual(["dense", "hybrid", "sparse"]);
    expect(report.modes.sparse!.semantic).toBe(true);
    expect(report.modes.dense!.semantic).toBe(false);
    expect(report.modes.hybrid!.semantic).toBe(false);
    for (const mode of Object.values(report.modes)) {
      expect(mode.per_query).toHaveLength(8);
      expect(mode.hit_rate_at_k).toBeCloseTo(mean(mode.per_query.map((q) => (q.hit ? 1 : 0))));
      expect(mode.mrr).toBeCloseTo(mean(mode.per_query.map((q) => q.reciprocal_rank)));
      expect(mode.ndcg_at_k).toBeCloseTo(mean(mode.per_query.map((q) => q.ndcg)));
      expect(mode.per_query.every((q) => q.relevances.length <= 5)).toBe(true);
    }
    expect(report.modes.sparse!.hit_rate_at_k).toBeGreaterThanOrEqual(0.5);
  });

  it("rejects a top_k outside 1..20", () => {
    expect(() => evaluateCorpus(0)).toThrow();
    expect(() => evaluateCorpus(21)).toThrow();
  });
});

describe("agent SSE stream", () => {
  const collect = async (message: string, extra: Record<string, unknown> = {}): Promise<AgentStreamEvent[]> => {
    const events: AgentStreamEvent[] = [];
    for await (const event of streamAgentTurn({ message, ...extra })) events.push(event);
    return events;
  };

  it("emits tool_start -> tool_end(diagnostics) -> token chunks -> metadata(diagnostics)", async () => {
    const events = await collect("What safeguards protect the files that users upload?");
    const types = events.map((e) => e.type);
    expect(types[0]).toBe("tool_start");
    expect(types[1]).toBe("tool_end");
    expect(types.at(-1)).toBe("metadata");
    const firstToken = types.indexOf("token");
    expect(firstToken).toBeGreaterThan(1);
    expect(types.slice(firstToken, -1).every((t) => t === "token")).toBe(true);
    expect(types.filter((t) => t === "token").length).toBeGreaterThan(3);

    const start = events[0] as Extract<AgentStreamEvent, { type: "tool_start" }>;
    expect(start.tool_name).toBe("search_knowledge_base");
    const end = events[1] as Extract<AgentStreamEvent, { type: "tool_end" }>;
    expect(end.diagnostics?.db_dialect).toBe("in-memory");
    expect(end.duration_ms).toBeGreaterThanOrEqual(0);
    const meta = events.at(-1) as Extract<AgentStreamEvent, { type: "metadata" }>;
    expect(meta.session_id).toMatch(/^[0-9a-f-]{36}$/);
    expect(meta.message_id).toMatch(/^[0-9a-f-]{36}$/);
    expect(meta.message_id).not.toBe(meta.session_id);
    expect(meta.diagnostics).not.toBeNull();
    expect(meta.citations.length).toBeGreaterThan(0);
    expect(meta.executed_tools[0]?.tool_name).toBe("search_knowledge_base");
    expect(Object.keys(meta).sort()).toEqual(
      ["citations", "diagnostics", "duration_ms", "executed_tools", "message_id", "session_id", "type"].sort(),
    );
  });

  it("keeps a provided session id and generates a downloadable report when asked for a PDF", async () => {
    const sessionId = "6a1c7f80-1e5b-4a0c-9d55-3b8f2d9e4c11";
    const events = await collect("Generate a PDF report about inference costs", { session_id: sessionId });
    const tools = events.filter((e) => e.type === "tool_end").map((e) => e.tool_name);
    expect(tools).toEqual(["search_knowledge_base", "generate_report_pdf"]);
    const text = events.flatMap((e) => (e.type === "token" ? [e.content] : [])).join("");
    const link = /\/api\/reports\/([A-Za-z0-9._-]+\.pdf)/.exec(text);
    expect(link).not.toBeNull();
    expect(decodeReportFilename(link![1]!)).toBe("Generate a PDF report about inference costs");
    const meta = events.at(-1) as Extract<AgentStreamEvent, { type: "metadata" }>;
    expect(meta.session_id).toBe(sessionId);
  });

  it("encodes events as SSE data frames", () => {
    expect(encodeSse({ type: "token", content: "hi" })).toBe('data: {"type":"token","content":"hi"}\n\n');
  });
});

describe("PDF reports", () => {
  it("builds a structurally valid PDF", () => {
    const bytes = buildPdf({ title: "Report (Q3) \\ test", sections: [{ heading: "Résumé", lines: ["x".repeat(500)] }] });
    const text = pdfText(bytes);
    expect(text.startsWith("%PDF-")).toBe(true);
    expect(text.trimEnd().endsWith("%%EOF")).toBe(true);
    const startxref = Number(/startxref\n(\d+)/.exec(text)![1]);
    expect(text.slice(startxref, startxref + 4)).toBe("xref");
    expect(text).toContain("Report \\(Q3\\) \\\\ test");
  });

  it("round-trips the query through the report filename", () => {
    const name = reportFilenameFor("¿Ingresos de LATAM?");
    expect(name).toMatch(/^showcase-report-[A-Za-z0-9_-]+\.pdf$/);
    expect(decodeReportFilename(name)).toBe("¿Ingresos de LATAM?");
    expect(decodeReportFilename("reporte_123.pdf")).toBeNull();
  });
});

describe("showcase locale (es/en)", () => {
  const answerOf = async (message: string, language?: "es" | "en" | "auto"): Promise<string> => {
    let text = "";
    for await (const event of streamAgentTurn({ message, ...(language ? { language } : {}) })) {
      if (event.type === "token") text += event.content;
    }
    return text;
  };

  it("answers in Spanish or English as requested, defaulting to English", async () => {
    expect(await answerOf("HNSW m ef_construction", "es")).toContain("Esto es lo que dice el Golden Corpus");
    expect(await answerOf("HNSW m ef_construction", "en")).toContain("Here is what the Golden Corpus says");
    expect(await answerOf("HNSW m ef_construction")).toContain("Here is what the Golden Corpus says");
  });

  it("detects the language of the question when language is auto", async () => {
    expect(await answerOf("¿Qué parámetros usa el índice HNSW?", "auto")).toContain("Esto es lo que dice el Golden Corpus");
    expect(await answerOf("Which parameters does the HNSW index use?", "auto")).toContain("Here is what the Golden Corpus says");
  });

  it("names the report tool input and download link in the requested language", async () => {
    const events: AgentStreamEvent[] = [];
    for await (const e of streamAgentTurn({ message: "Genera un informe PDF sobre costes de inferencia", language: "es" })) events.push(e);
    const reportStart = events.find((e) => e.type === "tool_start" && e.tool_name === "generate_report_pdf");
    expect(reportStart).toMatchObject({ tool_input: { title: "Informe Ejecutivo de Conocimiento" } });
    const text = events.flatMap((e) => (e.type === "token" ? [e.content] : [])).join("");
    expect(text).toContain("[Descargar informe](/api/reports/");
    const name = /\/api\/reports\/([A-Za-z0-9._-]+\.pdf)/.exec(text)![1]!;
    expect(decodeReportFilename(name)).toBe("Genera un informe PDF sobre costes de inferencia");
    expect(decodeReportLocale(name)).toBe("es");
  });

  it("writes evaluation warnings in the requested language", () => {
    expect(evaluateCorpus(5, "es").warnings?.[0]).toMatch(/no son semánticas/);
    expect(evaluateCorpus(5, "en").warnings?.[0]).toBe(SHOWCASE_EVALUATION_WARNING);
  });

  it("builds the report PDF in es and en, keeping legacy filenames English", () => {
    expect(pdfText(buildReportPdf("ingresos por región", "es"))).toContain("Informe Ejecutivo de Conocimiento");
    expect(pdfText(buildReportPdf("revenue by region", "en"))).toContain("Executive Knowledge Report");
    expect(reportFilenameFor("q", "es")).toMatch(/^showcase-report-[A-Za-z0-9_-]+\.es\.pdf$/);
    expect(decodeReportLocale(reportFilenameFor("q"))).toBe("en");
  });

  it("exports the transcript with localized labels", () => {
    const messages = [
      { role: "user" as const, content: "hola", created_at: "2026-01-01T00:00:00Z" },
      { role: "assistant" as const, content: "respuesta", created_at: "2026-01-01T00:00:01Z", citations: [{ document_name: "a.pdf", page_number: 1, chunk_type: "text" }] },
    ];
    const md = String(exportTranscript("s1", messages, "markdown", "es").body);
    expect(md).toContain("## Usuario");
    expect(md).toContain("## Agente");
    expect(md).toContain("**Fuentes:**");
    expect(String(exportTranscript("s1", messages, "markdown", "en").body)).toContain("## User");
    expect(pdfText(exportTranscript("s1", messages, "pdf", "es").body as Uint8Array)).toContain("Usuario - ");
  });
});
