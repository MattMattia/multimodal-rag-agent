import { bffError, liveOrShowcase, showcaseJson, showcaseResponse } from "@/lib/server/backend";
import { isReportFilename } from "@/lib/server/validation";
import { buildReportPdf, decodeReportFilename } from "@/lib/showcase-engine";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ filename: string }> }): Promise<Response> {
  const { filename } = await params;
  if (!isReportFilename(filename)) return bffError(400, "invalid report filename");
  return liveOrShowcase(`/reports/${encodeURIComponent(filename)}`, { signal: request.signal, timeoutMs: 8000 }, () => {
    const question = decodeReportFilename(filename);
    if (!question) return showcaseJson({ detail: "Report not found." }, 404);
    return showcaseResponse(buildReportPdf(question) as BodyInit, "application/pdf", {
      "Content-Disposition": `inline; filename="${filename}"`,
    });
  });
}
