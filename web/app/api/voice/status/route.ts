import { backendFetch } from "@/lib/backend";

export async function GET() {
  const res = await backendFetch("/voice/status");
  return Response.json(await res.json(), { status: res.status });
}
