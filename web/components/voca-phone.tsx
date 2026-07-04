"use client";

import { Phone, PhoneCall } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

export function VocaPhone({
  connectionId,
  xeroConnected,
}: {
  connectionId: string;
  xeroConnected: boolean;
}) {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [linkedPhone, setLinkedPhone] = useState<string | null>(null);
  const [vocaNumber, setVocaNumber] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    const [statusRes, linkRes] = await Promise.all([
      fetch("/api/voice/status"),
      fetch(`/api/voice/link?connection_id=${encodeURIComponent(connectionId)}`),
    ]);
    if (statusRes.ok) {
      const status = await statusRes.json();
      setVocaNumber(status.phone_number ?? null);
    }
    if (linkRes.ok) {
      const link = await linkRes.json();
      setLinkedPhone(link.phone_e164 ?? null);
    }
  }, [connectionId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleLink = async () => {
    setSaving(true);
    setMessage("");
    try {
      const res = await fetch("/api/voice/link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          connection_id: connectionId,
          phone_number: phoneNumber,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to link phone");
      setLinkedPhone(data.phone_e164);
      setMessage("Number linked — call Voca anytime.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to link");
    } finally {
      setSaving(false);
    }
  };

  if (!vocaNumber) {
    return (
      <div className="rounded-xl border border-white/[0.06] bg-zinc-900/40 p-4 text-sm text-zinc-500">
        <div className="flex items-center gap-2 text-zinc-400">
          <Phone className="size-4" />
          <span className="font-medium">Call Voca</span>
        </div>
        <p className="mt-2 text-xs leading-relaxed">
          Set <code className="text-zinc-400">VOCA_PHONE_NUMBER</code> and run{" "}
          <code className="text-zinc-400">python scripts/setup_elevenlabs_phone.py</code>{" "}
          to enable your phone line.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[#13b5ea]/20 bg-gradient-to-br from-[#13b5ea]/10 to-transparent p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-[#7dd3fc]">
            <PhoneCall className="size-4" />
            Call your bookkeeper
          </div>
          <a
            href={`tel:${vocaNumber}`}
            className="mt-1 block text-lg font-semibold tracking-tight text-white hover:text-[#7dd3fc]"
          >
            {vocaNumber}
          </a>
          <p className="mt-1 text-xs text-zinc-500">
            Delegate invoices, check what you&apos;re owed, ask about your books — by voice.
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        <label className="text-xs text-zinc-500">Your mobile (so Voca knows it&apos;s you)</label>
        <div className="flex gap-2">
          <input
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            placeholder={linkedPhone ?? "+44 7700 900123"}
            className="flex-1 rounded-lg border border-white/[0.08] bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600"
          />
          <button
            type="button"
            onClick={handleLink}
            disabled={saving || !phoneNumber.trim()}
            className="rounded-lg bg-[#13b5ea]/20 px-3 py-2 text-xs font-medium text-[#7dd3fc] hover:bg-[#13b5ea]/30 disabled:opacity-40"
          >
            {saving ? "…" : "Link"}
          </button>
        </div>
        {linkedPhone && (
          <p className="text-xs text-emerald-400/90">Linked: {linkedPhone}</p>
        )}
        {!xeroConnected && (
          <p className="text-xs text-amber-200/80">Connect Xero first so calls can access your books.</p>
        )}
        {message && <p className="text-xs text-zinc-400">{message}</p>}
      </div>
    </div>
  );
}
