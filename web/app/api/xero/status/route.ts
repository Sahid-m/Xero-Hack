const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const sessionId = searchParams.get("session_id");
  if (!sessionId) {
    return Response.json({ error: "session_id required" }, { status: 400 });
  }

  const res = await fetch(
    `${BACKEND_URL}/auth/xero/status?session_id=${encodeURIComponent(sessionId)}`,
  );
  const data = await res.json();
  return Response.json(data);
}
