/** Resume-stream endpoint — no active stream after page load. */
export async function GET() {
  return new Response(null, { status: 204 });
}
