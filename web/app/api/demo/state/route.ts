import { NextRequest } from "next/server";
import { backendFetch } from "@/lib/backend";

export async function GET(req: NextRequest) {
  const connectionId = req.nextUrl.searchParams.get("connection_id");
  if (!connectionId) {
    return Response.json({ error: "connection_id required" }, { status: 400 });
  }
  const res = await backendFetch(
    `/api/demo/state?connection_id=${encodeURIComponent(connectionId)}`,
  );
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
