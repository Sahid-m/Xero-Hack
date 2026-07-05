"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { getOrCreateConnectionId } from "@/lib/storage";

type DemoState = {
  connected: boolean;
  org_name: string | null;
  owed_total_gbp: number | null;
  owed_invoice_count: number | null;
  last_invoice: {
    status: string;
    customer: string;
    amount_gbp: number;
    invoice_number: string | null;
  } | null;
  last_receipt: {
    vendor: string;
    amount_gbp: number;
    category: string;
    in_xero: boolean;
    bill_number: string | null;
  } | null;
  updated_at: string | null;
};

function money(n: number | null | undefined) {
  if (n == null) return "—";
  return `£${n.toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function DemoMirrorPage() {
  const [connectionId, setConnectionId] = useState("");
  const [state, setState] = useState<DemoState | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setConnectionId(getOrCreateConnectionId());
  }, []);

  const fetchState = useCallback(async () => {
    if (!connectionId) return;
    try {
      const res = await fetch(
        `/api/demo/state?connection_id=${encodeURIComponent(connectionId)}`,
      );
      if (!res.ok) throw new Error("Failed to load demo state");
      const data = (await res.json()) as DemoState;
      setState(data);
      setError(null);
    } catch {
      setError("Could not reach Voca backend — is uvicorn running?");
    }
  }, [connectionId]);

  useEffect(() => {
    if (!connectionId) return;
    fetchState();
    const id = setInterval(fetchState, 2000);
    return () => clearInterval(id);
  }, [connectionId, fetchState]);

  async function uploadReceipt(file: File) {
    if (!connectionId) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(
        `/api/receipts/upload?connection_id=${encodeURIComponent(connectionId)}`,
        { method: "POST", body: form },
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || data.error || "Upload failed");
      }
      await fetchState();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <main className="voca-bg flex min-h-dvh flex-col items-center px-4 py-8">
      <div className="w-full max-w-lg space-y-6">
        <header className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-widest text-[#13b5ea]/80">Voca Mirror</p>
            <h1 className="text-2xl font-semibold text-white">Live Xero state</h1>
            <p className="mt-1 text-sm text-white/50">
              Updates as WhatsApp messages and voice notes hit your books.
            </p>
          </div>
          <Link
            href="/"
            className="shrink-0 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/70 hover:bg-white/5"
          >
            Chat fallback
          </Link>
        </header>

        {error && (
          <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            {error}
          </p>
        )}

        <section className="rounded-2xl border border-white/10 bg-[#111113]/90 p-6 shadow-xl">
          <div className="mb-6 flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${state?.connected ? "bg-emerald-400" : "bg-amber-400"}`}
            />
            <span className="text-sm text-white/70">
              {state?.connected
                ? `Connected · ${state.org_name ?? "Xero"}`
                : "Not connected — connect Xero first"}
            </span>
          </div>

          <div className="space-y-5">
            <div>
              <p className="text-xs uppercase tracking-wide text-white/40">Owed to you</p>
              <p className="text-4xl font-bold tabular-nums text-[#13b5ea]">
                {money(state?.owed_total_gbp ?? null)}
              </p>
              {state?.owed_invoice_count != null && (
                <p className="text-sm text-white/50">
                  {state.owed_invoice_count} unpaid invoice
                  {state.owed_invoice_count === 1 ? "" : "s"}
                </p>
              )}
            </div>

            {state?.last_receipt && (
              <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3">
                <p className="text-xs uppercase text-white/40">Last receipt</p>
                <p className="font-medium text-white">
                  {state.last_receipt.vendor} · {money(state.last_receipt.amount_gbp)}
                </p>
                <p className="text-sm text-white/50">{state.last_receipt.category}</p>
                <p className="mt-1 text-xs text-emerald-400/90">
                  {state.last_receipt.in_xero
                    ? `In Xero${state.last_receipt.bill_number ? ` · ${state.last_receipt.bill_number}` : ""}`
                    : "Pending — say add to Xero"}
                </p>
              </div>
            )}

            {state?.last_invoice && (
              <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3">
                <p className="text-xs uppercase text-white/40">Last invoice</p>
                <p className="font-medium text-white">
                  {state.last_invoice.customer} · {money(state.last_invoice.amount_gbp)}
                </p>
                <p className="text-sm capitalize text-white/50">
                  {state.last_invoice.status}
                  {state.last_invoice.invoice_number
                    ? ` · ${state.last_invoice.invoice_number}`
                    : ""}
                </p>
              </div>
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-[#111113]/60 p-4">
          <p className="mb-3 text-sm text-white/60">Upload receipt (demo stub → Shell £47.50)</p>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) uploadReceipt(f);
            }}
          />
          <button
            type="button"
            disabled={uploading || !state?.connected}
            onClick={() => fileRef.current?.click()}
            className="w-full rounded-xl bg-[#13b5ea]/20 py-3 text-sm font-medium text-[#13b5ea] hover:bg-[#13b5ea]/30 disabled:opacity-40"
          >
            {uploading ? "Uploading…" : "Upload receipt photo"}
          </button>
        </section>

        {state?.updated_at && (
          <p className="text-center text-xs text-white/30">
            Last sync {new Date(state.updated_at).toLocaleTimeString()}
          </p>
        )}
      </div>
    </main>
  );
}
