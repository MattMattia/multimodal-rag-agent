import type { FeedbackResponse } from "@/lib/contracts";
import { bffError, liveOrShowcase, showcaseJson } from "@/lib/server/backend";
import { parseFeedbackRequest, readJson } from "@/lib/server/validation";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  const parsed = parseFeedbackRequest(await readJson(request));
  if (!parsed.ok) return bffError(422, parsed.error);
  return liveOrShowcase("/agent/feedback", { signal: request.signal, method: "POST", json: parsed.value }, () => {
    // Acknowledged but not persisted: the serverless showcase has no database.
    const body: FeedbackResponse = { status: "ok", message_id: parsed.value.message_id, rating: parsed.value.rating };
    return showcaseJson(body);
  });
}
