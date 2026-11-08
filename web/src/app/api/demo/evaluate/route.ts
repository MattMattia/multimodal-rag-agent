import { bffError, liveOrShowcase, showcaseJson } from "@/lib/server/backend";
import { parseEvaluateRequest, readJson } from "@/lib/server/validation";
import { evaluateCorpus } from "@/lib/showcase-engine";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  const parsed = parseEvaluateRequest(await readJson(request));
  if (!parsed.ok) return bffError(422, parsed.error);
  // The live benchmark runs 24 searches (plus Gemini calls) before answering, so it gets more time.
  return liveOrShowcase("/demo/evaluate", { signal: request.signal, method: "POST", json: parsed.value, timeoutMs: 90_000 }, () =>
    showcaseJson(evaluateCorpus(parsed.value.top_k ?? 5)),
  );
}
