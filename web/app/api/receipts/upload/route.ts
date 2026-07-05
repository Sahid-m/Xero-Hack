import { NextRequest } from "next/server";
import { BACKEND_URL } from "@/lib/backend";

export async function POST(req: NextRequest) {
  const connectionId = req.nextUrl.searchParams.get("connection_id");
  if (!connectionId) {
    return Response.json({ error: "connection_id required" }, { status: 400 });
  }

  const form = await req.formData();
  const file = form.get("file");
  const body = new FormData();
  if (file instanceof Blob) {
    body.append("file", file);
  }

  const res = await fetch(
    `${BACKEND_URL}/receipts/upload?connection_id=${encodeURIComponent(connectionId)}`,
    { method: "POST", body },
  );
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
