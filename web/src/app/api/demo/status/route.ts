import type { BffDemoStatus, DemoStatusResponse } from "@/lib/contracts";
import { callBackend, clientClosed, passThrough, showcaseJson } from "@/lib/server/backend";
import { showcaseStatus } from "@/lib/showcase-engine";

export const dynamic = "force-dynamic";

/** Demo status plus `source`, which drives the live/showcase indicator in the top bar. */
export async function GET(request?: Request): Promise<Response> {
  const result = await callBackend("/demo/status", { signal: request?.signal, timeoutMs: 2500 });
  if (result.kind === "aborted") return clientClosed();
  if (result.kind === "unreachable") return showcaseJson(showcaseStatus());
  // A live backend that cannot report its status (e.g. 401 with a wrong key) is surfaced, not hidden.
  if (!result.response.ok) return passThrough(result.response);
  const live = (await result.response.json()) as DemoStatusResponse;
  const body: BffDemoStatus = { ...live, source: "fastapi" };
  return Response.json(body, { headers: { "x-rag-source": "fastapi", "Cache-Control": "no-store" } });
}
