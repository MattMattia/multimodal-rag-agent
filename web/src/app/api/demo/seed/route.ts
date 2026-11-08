import { liveOrShowcase, showcaseJson } from "@/lib/server/backend";
import { showcaseSeed } from "@/lib/showcase-engine";

export const dynamic = "force-dynamic";

export async function POST(request?: Request): Promise<Response> {
  const started = performance.now();
  return liveOrShowcase("/demo/seed", { signal: request?.signal, method: "POST", timeoutMs: 30_000 }, () =>
    showcaseJson(showcaseSeed(performance.now() - started)),
  );
}
