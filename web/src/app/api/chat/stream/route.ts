import type { AgentChatRequest } from "@/lib/contracts";
import { bffError, callBackend, clientClosed, passThrough } from "@/lib/server/backend";
import { parseChatRequest, readJson } from "@/lib/server/validation";
import { ShowcaseError, assertSearchableDocument, encodeSse, streamAgentTurn } from "@/lib/showcase-engine";

export const dynamic = "force-dynamic";

const SSE_HEADERS = {
  "Content-Type": "text/event-stream; charset=utf-8",
  "Cache-Control": "no-cache, no-transform",
  Connection: "keep-alive",
  "X-Accel-Buffering": "no",
  "x-rag-source": "showcase",
};

/** Forward only the fields the client sent, so backend defaults (e.g. the agent top_k) still apply. */
function forwardedBody(original: Record<string, unknown>, parsed: AgentChatRequest): Record<string, unknown> {
  return Object.fromEntries(Object.entries(parsed).filter(([key]) => original[key] !== undefined));
}

function showcaseStream(request: AgentChatRequest): Response {
  const encoder = new TextEncoder();
  const events = streamAgentTurn(request);
  const stream = new ReadableStream<Uint8Array>({
    async pull(controller) {
      const next = await events.next();
      if (next.done) controller.close();
      else controller.enqueue(encoder.encode(encodeSse(next.value)));
    },
    async cancel() {
      await events.return(undefined);
    },
  });
  return new Response(stream, { headers: SSE_HEADERS });
}

export async function POST(request: Request): Promise<Response> {
  const raw = await readJson(request);
  const parsed = parseChatRequest(raw);
  if (!parsed.ok) return bffError(422, parsed.error);

  const result = await callBackend("/agent/chat/stream", {
    signal: request.signal,
    method: "POST",
    json: forwardedBody(raw as Record<string, unknown>, parsed.value),
    timeoutMs: 15_000,
  });
  if (result.kind === "live") {
    const live = passThrough(result.response);
    live.headers.set("X-Accel-Buffering", "no");
    return live;
  }
  if (result.kind === "aborted") return clientClosed();
  try {
    assertSearchableDocument(parsed.value.filter_document_id ?? null);
  } catch (error) {
    if (error instanceof ShowcaseError) return bffError(error.status, error.message);
    throw error;
  }
  return showcaseStream(parsed.value);
}
