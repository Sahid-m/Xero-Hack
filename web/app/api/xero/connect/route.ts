import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(req: NextRequest) {
  const connectionId =
    req.nextUrl.searchParams.get("connection_id") ??
    req.nextUrl.searchParams.get("session_id");
  if (!connectionId) {
    return Response.json({ error: "connection_id required" }, { status: 400 });
  }

  return Response.redirect(
    `${BACKEND_URL}/auth/xero?connection_id=${encodeURIComponent(connectionId)}`,
    302,
  );
}
