import { bffError, liveOrShowcase, showcaseResponse } from "@/lib/server/backend";
import { isUuid, parseExportFormat, parseLang, parseTranscript, readJson } from "@/lib/server/validation";
import { exportTranscript } from "@/lib/showcase-engine";

export const dynamic = "force-dynamic";

/**
 * Live: proxies GET /agent/sessions/{id}/export (the stored conversation), forwarding `lang` when sent.
 * Offline: the browser posts its in-tab transcript, which the showcase engine renders in that language.
 */
export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await params;
  if (!isUuid(id)) return bffError(400, "session id must be a UUID");
  const query = new URL(request.url).searchParams;
  const format = parseExportFormat(query.get("format"));
  if (!format.ok) return bffError(422, format.error);
  const lang = parseLang(query.get("lang"));
  if (!lang.ok) return bffError(422, lang.error);
  const body = await readJson(request);
  const upstream = `/agent/sessions/${id}/export?format=${format.value}${lang.value ? `&lang=${lang.value}` : ""}`;

  return liveOrShowcase(upstream, { signal: request.signal, timeoutMs: 10_000 }, () => {
    const transcript = parseTranscript(body);
    if (!transcript.ok) return bffError(422, transcript.error);
    const file = exportTranscript(id, transcript.value, format.value, lang.value ?? undefined);
    return showcaseResponse(file.body as BodyInit, file.contentType, {
      "Content-Disposition": `attachment; filename="${file.filename}"`,
    });
  });
}
