import { bffError, liveOrShowcase, showcaseJson, showcaseResponse } from "@/lib/server/backend";
import { isUuid } from "@/lib/server/validation";
import { findImage, renderDiagramSvg } from "@/lib/showcase-engine";

export const dynamic = "force-dynamic";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string; imageId: string }> },
): Promise<Response> {
  const { id, imageId } = await params;
  if (!isUuid(id) || !isUuid(imageId)) return bffError(400, "document and image ids must be UUIDs");
  return liveOrShowcase(`/documents/${id}/images/${imageId}/file`, { signal: request.signal, timeoutMs: 8000 }, () => {
    const image = findImage(id, imageId);
    if (!image) return showcaseJson({ detail: "Image not found." }, 404);
    return showcaseResponse(renderDiagramSvg(image), "image/svg+xml; charset=utf-8", {
      "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
    });
  });
}
