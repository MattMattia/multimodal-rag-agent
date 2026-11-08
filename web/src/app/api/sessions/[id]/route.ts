import { bffError, liveOrShowcase } from "@/lib/server/backend";
import { isUuid } from "@/lib/server/validation";

export const dynamic = "force-dynamic";

export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await params;
  if (!isUuid(id)) return bffError(400, "session id must be a UUID");
  return liveOrShowcase(
    `/agent/sessions/${id}`,
    { signal: request.signal, method: "DELETE" },
    () => new Response(null, { status: 204, headers: { "x-rag-source": "showcase" } }),
  );
}
