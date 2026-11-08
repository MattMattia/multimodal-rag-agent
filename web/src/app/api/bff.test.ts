import { GET as getStatus } from "./demo/status/route";
import { POST as postChat } from "./chat/stream/route";
import { GET as getReport } from "./reports/[filename]/route";
import { GET as getImage } from "./documents/[id]/images/[imageId]/route";
import { POST as postSearch } from "./search/route";
import { GET as getSessions } from "./sessions/route";
import { POST as postDocument } from "./documents/route";
import { GOLDEN_DOCUMENTS, reportFilenameFor } from "@/lib/showcase-engine";

const params = <T,>(value: T) => ({ params: Promise.resolve(value) });
const jsonRequest = (url: string, body: unknown) =>
  new Request(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("FASTAPI_URL", "http://backend.test:8000");
  vi.stubEnv("API_KEY", "secret-key");
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("BFF fallback to the showcase engine", () => {
  it("falls back when the backend is unreachable (fetch rejects)", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
    const response = await getStatus();
    expect(response.status).toBe(200);
    expect(response.headers.get("x-rag-source")).toBe("showcase");
    const body = await response.json();
    expect(body).toMatchObject({ source: "showcase", db_dialect: "in-memory", demo_seeded: true, total_documents: 3 });
  });

  it("falls back when FASTAPI_URL is not configured, without calling fetch", async () => {
    vi.stubEnv("FASTAPI_URL", "");
    const response = await getSessions();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(response.headers.get("x-rag-source")).toBe("showcase");
    expect(await response.json()).toEqual([]);
  });

  it("falls back on a timeout (aborted request)", async () => {
    vi.stubEnv("FASTAPI_TIMEOUT_MS", "20");
    fetchMock.mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
        }),
    );
    const response = await getSessions();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(response.headers.get("x-rag-source")).toBe("showcase");
  });

  it("falls back on 502/504 gateway errors and logs the reason without secrets", async () => {
    fetchMock.mockResolvedValue(new Response("bad gateway", { status: 502 }));
    const response = await getSessions();
    expect(response.headers.get("x-rag-source")).toBe("showcase");
    const logged = vi.mocked(console.warn).mock.calls.flat().join(" ");
    expect(logged).toContain("gateway returned 502");
    expect(logged).not.toContain("secret-key");
    expect(logged).not.toContain("backend.test");
  });

  it("passes a deliberate 503 from a live backend through", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ detail: "maintenance" }), { status: 503 }));
    const response = await getSessions();
    expect(response.status).toBe(503);
    expect(response.headers.get("x-rag-source")).toBe("fastapi");
  });

  it("propagates the client disconnect to the upstream FastAPI stream", async () => {
    let upstreamSignal: AbortSignal | undefined;
    fetchMock.mockImplementation(async (_url, init) => {
      upstreamSignal = init?.signal ?? undefined;
      return new Response(new ReadableStream({ start() {} }), { headers: { "Content-Type": "text/event-stream" } });
    });
    const client = new AbortController();
    const request = new Request("http://web.test/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "hola" }),
      signal: client.signal,
    });
    const response = await postChat(request);
    expect(response.headers.get("x-rag-source")).toBe("fastapi");
    expect(upstreamSignal?.aborted).toBe(false);
    client.abort();
    expect(upstreamSignal?.aborted).toBe(true);
  });

  it("passes a live 404 through instead of falling back", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ detail: "Reporte no encontrado." }), { status: 404, headers: { "Content-Type": "application/json" } }));
    const response = await getReport(new Request("http://web.test/api/reports/reporte_1_x.pdf"), params({ filename: "reporte_1_x.pdf" }));
    expect(response.status).toBe(404);
    expect(response.headers.get("x-rag-source")).toBe("fastapi");
    expect(await response.json()).toEqual({ detail: "Reporte no encontrado." });
  });

  it("sends the API key from the server and enriches the live status with source", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ db_dialect: "postgresql", demo_seeded: true, total_documents: 3, total_chunks: 30, total_images: 3, gemini_configured: true, langfuse_enabled: false, active_models: {}, embedding_mode: "gemini" }), { status: 200 }),
    );
    const response = await getStatus();
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://backend.test:8000/api/v1/demo/status");
    expect(new Headers(init?.headers).get("X-API-Key")).toBe("secret-key");
    expect(await response.json()).toMatchObject({ source: "fastapi", db_dialect: "postgresql" });
  });
});

describe("BFF parameter validation", () => {
  it("rejects a report filename with path traversal before proxying", async () => {
    const response = await getReport(new Request("http://web.test/api/reports/x"), params({ filename: "..%2F..%2Fetc.pdf" }));
    expect(response.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects non-UUID image ids before proxying", async () => {
    const response = await getImage(new Request("http://web.test/x"), params({ id: "not-a-uuid", imageId: "1" }));
    expect(response.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects an oversized upload from Content-Length before reading the body", async () => {
    const request = new Request("http://web.test/api/documents", {
      method: "POST",
      headers: { "Content-Type": "multipart/form-data; boundary=x", "Content-Length": String(30 * 1024 * 1024) },
      body: "--x--",
    });
    const formData = vi.spyOn(request, "formData");
    const response = await postDocument(request);
    expect(response.status).toBe(413);
    expect(formData).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects an invalid chat body with 422", async () => {
    const response = await postChat(jsonRequest("http://web.test/api/chat/stream", { message: "", top_k: 99 }));
    expect(response.status).toBe(422);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("showcase artefacts", () => {
  beforeEach(() => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
  });

  it("answers /api/search with the hybrid showcase ranking", async () => {
    const response = await postSearch(jsonRequest("http://web.test/api/search", { query: "HNSW m=16", top_k: 2 }));
    expect(response.headers.get("x-rag-source")).toBe("showcase");
    const body = await response.json();
    expect(body.results).toHaveLength(2);
    expect(body.diagnostics.db_dialect).toBe("in-memory");
  });

  it("streams SSE events in order", async () => {
    const response = await postChat(jsonRequest("http://web.test/api/chat/stream", { message: "¿Qué parámetros usa el índice HNSW?" }));
    expect(response.headers.get("content-type")).toContain("text/event-stream");
    const frames = (await response.text()).split("\n\n").filter(Boolean);
    const types = frames.map((f) => JSON.parse(f.replace(/^data: /, "")).type as string);
    expect(types.slice(0, 2)).toEqual(["tool_start", "tool_end"]);
    expect(types.at(-1)).toBe("metadata");
    expect(types.includes("token")).toBe(true);
  });

  it("serves a valid PDF for a showcase report filename", async () => {
    const filename = reportFilenameFor("ingresos por región");
    const response = await getReport(new Request(`http://web.test/api/reports/${filename}`), params({ filename }));
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("application/pdf");
    const bytes = new Uint8Array(await response.arrayBuffer());
    expect(String.fromCharCode(...bytes.slice(0, 5))).toBe("%PDF-");
  });

  it("returns 404 for an unknown report while offline", async () => {
    const response = await getReport(new Request("http://web.test/api/reports/reporte_1.pdf"), params({ filename: "reporte_1.pdf" }));
    expect(response.status).toBe(404);
  });

  it("serves the golden diagram as SVG", async () => {
    const doc = GOLDEN_DOCUMENTS[1]!;
    const response = await getImage(new Request("http://web.test/x"), params({ id: doc.id, imageId: doc.image.id }));
    expect(response.headers.get("content-type")).toContain("image/svg+xml");
    expect(await response.text()).toContain("<svg");
  });
});
