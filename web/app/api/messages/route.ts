import { NextRequest } from "next/server";
import { backendFetch } from "@/lib/backend";

export async function GET(req: NextRequest) {
  const sessionId = req.nextUrl.searchParams.get("session_id");
  if (!sessionId) {
    return Response.json({ error: "session_id required" }, { status: 400 });
  }

  const res = await backendFetch(
    `/api/messages?session_id=${encodeURIComponent(sessionId)}`,
  );
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function PUT(req: Request) {
  const body = await req.json();
  const res = await backendFetch("/api/messages", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}

export async function DELETE(req: NextRequest) {
  const sessionId = req.nextUrl.searchParams.get("session_id");
  if (!sessionId) {
    return Response.json({ error: "session_id required" }, { status: 400 });
  }

  const res = await backendFetch(
    `/api/messages?session_id=${encodeURIComponent(sessionId)}`,
    { method: "DELETE" },
  );
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
