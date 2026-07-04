import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const connectionId =
    searchParams.get("connection_id") ??
    searchParams.get("session_id");
  if (!connectionId) {
    return Response.json({ error: "connection_id required" }, { status: 400 });
  }

  const legacy = searchParams.get("legacy_session_ids") ?? "";
  const query = new URLSearchParams({
    connection_id: connectionId,
    legacy_session_ids: legacy,
  });

  const res = await fetch(`${BACKEND_URL}/auth/xero/status?${query}`);
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
