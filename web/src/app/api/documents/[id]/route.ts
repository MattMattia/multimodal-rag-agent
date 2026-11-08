import { bffError, liveOrShowcase, showcaseJson } from "@/lib/server/backend";
import { isUuid } from "@/lib/server/validation";
import { documentDetail } from "@/lib/showcase-engine";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await params;
  if (!isUuid(id)) return bffError(400, "document id must be a UUID");
  return liveOrShowcase(`/documents/${id}`, { signal: request.signal }, () => {
    const detail = documentDetail(id);
    return detail ? showcaseJson(detail) : showcaseJson({ detail: "Document not found." }, 404);
  });
}
