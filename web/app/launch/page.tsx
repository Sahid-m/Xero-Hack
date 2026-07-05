"use client";

import { useEffect, useState } from "react";

type Slide = {
  kicker: string;
  title: string;
  body?: string;
  stats?: { value: string; label: string }[];
};

const SLIDES: Slide[] = [
  {
    kicker: "The problem",
    title: "864,000 sole traders just became legally required to keep digital tax records",
    body: "Making Tax Digital for Income Tax — mandatory from 6 April 2026 for anyone earning over £50k. Quarterly digital updates, not annual. Most have never opened accounting software.",
    stats: [
      { value: "864,000", label: "sole traders & landlords, Wave 1 (HMRC, Feb 2026)" },
      { value: "~2.9M", label: "brought into MTD by 2028 across all waves" },
      { value: "4.57M", label: "total self-employed in the UK (ONS, Q1 2026)" },
    ],
  },
  {
    kicker: "The cost",
    title: "The admin burden is real, and it's expensive",
    stats: [
      { value: "24 days/yr", label: "lost to financial admin (Sage UK, 2025)" },
      { value: "£100–150+/mo", label: "typical UK bookkeeper cost, sole trader" },
      { value: "76%", label: "of UK adults use WhatsApp daily (Ofcom, 2025)" },
    ],
  },
  {
    kicker: "The gap Xero opened",
    title: "Xero already built this — then walked away from it",
    body: "JAX, Xero's own AI agent, had WhatsApp / SMS / email chat. Xero discontinued that access on 1 June 2026 — right as the MTD wave hit. JAX survives only inside the Xero app.",
    stats: [
      { value: "1 Jun 2026", label: "JAX WhatsApp/SMS/email support discontinued" },
      { value: "864,000+", label: "new mandatory users with nowhere to meet them" },
    ],
  },
  {
    kicker: "The solution",
    title: "Voca — Xero, run entirely from WhatsApp",
    body: "Photograph a receipt, it's read by a vision model. Ask what you're owed, it's live from Xero. Say \"reconcile my bank transactions,\" it matches payments to bills and closes them out. Ask if you're ready for your MTD update — get the real quarter, deadline, and a filing-ready tax pack.",
  },
  {
    kicker: "Why it's safe to ship",
    title: "Guardrails with real teeth, not just prompts",
    stats: [
      { value: "£0", label: "silent currency conversions — flags mismatches instead" },
      { value: "0", label: "duplicate bills — receipts marked added after write" },
      { value: "100%", label: "of writes are real Xero API calls, nothing simulated" },
    ],
  },
  {
    kicker: "Live now",
    title: "Every number you're about to see is real",
    body: "Pulled live from a connected Xero organisation during this demo. Nobody opens Xero.",
  },
];

export default function LaunchPage() {
  const [i, setI] = useState(0);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight" || e.key === " ") setI((n) => Math.min(n + 1, SLIDES.length - 1));
      if (e.key === "ArrowLeft") setI((n) => Math.max(n - 1, 0));
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const slide = SLIDES[i];

  return (
    <div
      className="min-h-screen w-full flex flex-col justify-between p-10 md:p-16 select-none cursor-pointer"
      style={{ background: "radial-gradient(circle at 20% 20%, #0f1720 0%, #070708 60%)" }}
      onClick={() => setI((n) => Math.min(n + 1, SLIDES.length - 1))}
    >
      <div className="flex items-center justify-between text-sm tracking-widest uppercase text-[#13b5ea] font-mono">
        <span>Voca</span>
        <span>
          {i + 1} / {SLIDES.length}
        </span>
      </div>

      <div className="max-w-4xl mx-auto text-center flex flex-col gap-8">
        <div className="text-[#13b5ea] uppercase tracking-[0.3em] text-sm md:text-base font-mono">
          {slide.kicker}
        </div>
        <h1 className="text-3xl md:text-6xl font-semibold leading-tight text-[#ededed]">
          {slide.title}
        </h1>
        {slide.body && (
          <p className="text-lg md:text-2xl text-[#a1a1aa] leading-relaxed max-w-3xl mx-auto">
            {slide.body}
          </p>
        )}
        {slide.stats && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-4">
            {slide.stats.map((s) => (
              <div
                key={s.label}
                className="rounded-2xl border border-white/10 bg-white/[0.03] p-6 flex flex-col gap-2"
              >
                <div className="text-3xl md:text-4xl font-bold text-[#13b5ea]">{s.value}</div>
                <div className="text-sm md:text-base text-[#a1a1aa]">{s.label}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs md:text-sm text-[#71717a] font-mono">
        <span>Xero Encode Hackathon — Bounty 01</span>
        <span>click / → to advance · ← back</span>
      </div>
    </div>
  );
}
