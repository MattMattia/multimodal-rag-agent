import type { ChatHistoryResponse } from "@/lib/contracts";
import { bffError, liveOrShowcase, showcaseJson } from "@/lib/server/backend";
import { isUuid } from "@/lib/server/validation";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await params;
  if (!isUuid(id)) return bffError(400, "session id must be a UUID");
  return liveOrShowcase(`/agent/sessions/${id}/history`, { signal: request.signal }, () => {
    const empty: ChatHistoryResponse = { session_id: id, total_messages: 0, messages: [] };
    return showcaseJson(empty);
  });
}
