import { backendFetch, normalizeChatBody, relayStreamResponse } from "@/lib/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(req: Request) {
  const body = (await req.json()) as Record<string, unknown>;

  const res = await backendFetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(normalizeChatBody(body)),
  });

  if (!res.ok) {
    const detail = await res.text();
    return new Response(detail || "Backend error", { status: res.status });
  }

  return relayStreamResponse(res);
}
