import { bffError, liveOrShowcase, showcaseJson } from "@/lib/server/backend";
import { parseSearchRequest, readJson } from "@/lib/server/validation";
import { searchCorpus } from "@/lib/showcase-engine";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  const parsed = parseSearchRequest(await readJson(request));
  if (!parsed.ok) return bffError(422, parsed.error);
  return liveOrShowcase("/search", { signal: request.signal, method: "POST", json: parsed.value, timeoutMs: 20_000 }, () =>
    showcaseJson(searchCorpus(parsed.value)),
  );
}
