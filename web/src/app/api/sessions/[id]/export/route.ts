import { bffError, liveOrShowcase, showcaseResponse } from "@/lib/server/backend";
import { isUuid, parseExportFormat, parseTranscript, readJson } from "@/lib/server/validation";
import { exportTranscript } from "@/lib/showcase-engine";

export const dynamic = "force-dynamic";

/**
 * Live: proxies GET /agent/sessions/{id}/export (the stored conversation).
 * Offline: the browser posts its in-tab transcript, which the showcase engine renders.
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await params;
  if (!isUuid(id)) return bffError(400, "session id must be a UUID");
  const format = parseExportFormat(new URL(request.url).searchParams.get("format"));
  if (!format.ok) return bffError(422, format.error);
  const body = await readJson(request);

  return liveOrShowcase(`/agent/sessions/${id}/export?format=${format.value}`, { signal: request.signal, timeoutMs: 10_000 }, () => {
    const transcript = parseTranscript(body);
    if (!transcript.ok) return bffError(422, transcript.error);
    const file = exportTranscript(id, transcript.value, format.value);
    return showcaseResponse(file.body as BodyInit, file.contentType, {
      "Content-Disposition": `attachment; filename="${file.filename}"`,
    });
  });
}
