import { liveOrShowcase, showcaseJson } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

/** Serverless instances keep no state: offline, sessions live only in the browser tab. */
export async function GET(request?: Request): Promise<Response> {
  return liveOrShowcase("/agent/sessions", { signal: request?.signal }, () => showcaseJson([]));
}
