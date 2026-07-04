import { NextRequest } from "next/server";
import { backendFetch } from "@/lib/backend";

export async function GET(req: NextRequest) {
  const connectionId =
    req.nextUrl.searchParams.get("connection_id") ??
    req.nextUrl.searchParams.get("session_id");
  if (!connectionId) {
    return Response.json({ error: "connection_id required" }, { status: 400 });
  }

  const res = await backendFetch(
    `/auth/xero?connection_id=${encodeURIComponent(connectionId)}`,
    { redirect: "manual" },
  );

  const location = res.headers.get("location");
  if (location) {
    return Response.redirect(location, 302);
  }

  const detail = await res.text();
  return new Response(detail || "Failed to start Xero OAuth", { status: res.status });
}
