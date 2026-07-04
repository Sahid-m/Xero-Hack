import { NextRequest } from "next/server";
import { backendFetch } from "@/lib/backend";

export async function GET(req: NextRequest) {
  const connectionId = req.nextUrl.searchParams.get("connection_id");
  if (!connectionId) {
    return Response.json({ error: "connection_id required" }, { status: 400 });
  }
  const res = await backendFetch(
    `/api/voice/link?connection_id=${encodeURIComponent(connectionId)}`,
  );
  return Response.json(await res.json(), { status: res.status });
}

export async function POST(req: Request) {
  const body = await req.json();
  const res = await backendFetch("/api/voice/link", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return Response.json(await res.json(), { status: res.status });
}

export async function DELETE(req: NextRequest) {
  const connectionId = req.nextUrl.searchParams.get("connection_id");
  if (!connectionId) {
    return Response.json({ error: "connection_id required" }, { status: 400 });
  }
  const res = await backendFetch(
    `/api/voice/link?connection_id=${encodeURIComponent(connectionId)}`,
    { method: "DELETE" },
  );
  return Response.json(await res.json(), { status: res.status });
}
