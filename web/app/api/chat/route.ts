const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
  const body = await req.json();

  const res = await fetch(`${BACKEND_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: body.messages,
      session_id: body.session_id ?? body.sessionId ?? body.id,
      connection_id: body.connection_id ?? body.connectionId,
      legacy_session_ids: body.legacy_session_ids ?? body.legacySessionIds ?? [],
    }),
  });

  if (!res.ok) {
    const detail = await res.text();
    return new Response(detail || "Backend error", { status: res.status });
  }

  const headers = new Headers();
  const streamHeader = res.headers.get("x-vercel-ai-ui-message-stream");
  if (streamHeader) {
    headers.set("x-vercel-ai-ui-message-stream", streamHeader);
  }
  headers.set("Content-Type", res.headers.get("Content-Type") ?? "text/event-stream");
  headers.set("Cache-Control", "no-cache");
  headers.set("Connection", "keep-alive");

  return new Response(res.body, { headers });
}
