import { bffError, liveOrShowcase, showcaseJson } from "@/lib/server/backend";
import { listDocuments } from "@/lib/showcase-engine";

export const dynamic = "force-dynamic";

const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const MULTIPART_OVERHEAD_BYTES = 64 * 1024;

export async function GET(request?: Request): Promise<Response> {
  return liveOrShowcase("/documents?limit=100", { signal: request?.signal }, () => showcaseJson(listDocuments()));
}

/** Multipart upload proxied to POST /documents/upload; ingestion needs the live backend. */
export async function POST(request: Request): Promise<Response> {
  // Reject oversized bodies before buffering them (multipart overhead is small next to the limit).
  const declared = Number(request.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES) {
    return bffError(413, "file exceeds the 25 MB upload limit");
  }
  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File) || file.size === 0) return bffError(422, "a non-empty file field is required");
  if (file.size > MAX_UPLOAD_BYTES) return bffError(413, "file exceeds the 25 MB upload limit");
  const forward = new FormData();
  forward.append("file", file, file.name);
  return liveOrShowcase("/documents/upload", { signal: request?.signal, method: "POST", body: forward, timeoutMs: 30_000 }, () =>
    showcaseJson(
      {
        detail:
          "Uploads need the live FastAPI backend (Gemini Vision + pgvector ingestion). The serverless showcase serves the read-only Golden Corpus.",
      },
      503,
    ),
  );
}
