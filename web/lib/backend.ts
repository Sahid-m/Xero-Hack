export const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function backendFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const url = path.startsWith("http") ? path : `${BACKEND_URL}${path}`;
  return fetch(url, init);
}

/** Relay an SSE/streaming response from the Python backend to the client. */
export function relayStreamResponse(res: Response): Response {
  if (!res.ok) {
    return res;
  }

  const headers = new Headers();
  const streamHeader = res.headers.get("x-vercel-ai-ui-message-stream");
  if (streamHeader) {
    headers.set("x-vercel-ai-ui-message-stream", streamHeader);
  }
  headers.set("Content-Type", res.headers.get("Content-Type") ?? "text/event-stream");
  headers.set("Cache-Control", "no-cache, no-transform");
  headers.set("Connection", "keep-alive");
  headers.set("X-Accel-Buffering", "no");

  return new Response(res.body, { status: res.status, headers });
}

/** Normalize chat/session fields from the AI SDK transport body. */
export function normalizeChatBody(body: Record<string, unknown>) {
  return {
    ...body,
    messages: body.messages,
    session_id: body.session_id ?? body.sessionId ?? body.id,
    connection_id: body.connection_id ?? body.connectionId,
    legacy_session_ids: body.legacy_session_ids ?? body.legacySessionIds ?? [],
  };
}
