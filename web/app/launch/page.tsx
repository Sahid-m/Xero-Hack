"use client";

import { useEffect, useState } from "react";

type Slide = {
  n: string;
  kicker: string;
  title: string;
  points: string[];
  stats?: { value: string; label: string }[];
  cta?: { label: string; href: string; primary?: boolean }[];
};

const DEMO_CONNECTION_ID = "conv_9501kwqfmzf0frwsza9pakj5spjz";
const WHATSAPP_CONNECT_URL =
  "https://wa.me/447424845871?text=/connect:40fa2cf6-3970-47c8-9e26-c12fe4e22793";

const SLIDES: Slide[] = [
  {
    n: "01",
    kicker: "The problem",
    title: "By April 2027, almost 2 million people will lean on an accountant they've never needed before",
    points: [
      "Making Tax Digital brings quarterly filing — not annual — starting with over £50k income",
      "Most have never opened accounting software, and most don't want to start now",
      "So they turn to an accountant — often for the first time in their life",
    ],
    stats: [
      { value: "864,000", label: "sole traders & landlords, Wave 1 — HMRC, Feb 2026" },
      { value: "~1.9M", label: "cumulative by April 2027, Waves 1 + 2" },
      { value: "4.57M", label: "total self-employed in the UK — ONS, Q1 2026" },
    ],
  },
  {
    n: "02",
    kicker: "Who we're for",
    title: "The barrier was never the tax rules — it was the software",
    points: [
      "A landlord or shop owner doesn't want a course in Xero — they want their books sorted",
      "They already know how to chat. Nobody taught them, and nobody has to",
      "And they don't want to pay accountant rates for every small question either",
    ],
    stats: [
      { value: "£100–150+/mo", label: "typical bookkeeper cost, before you've asked a single question" },
      { value: "76%", label: "of UK adults use WhatsApp daily — Ofcom, 2025" },
      { value: "24 days/yr", label: "lost to financial admin — Sage UK, 2025" },
    ],
  },
  {
    n: "03",
    kicker: "The generation entering self-employment now",
    title: "They grew up chatting, not filing — and first contact decides who keeps them",
    points: [
      "Side hustles, creator income, and gig work are how most young people first go self-employed",
      "Chat is the default interface for everything they already use — banking, support, shopping",
      "Whoever earns first contact doesn't win a feature — they win the relationship for a decade",
    ],
  },
  {
    n: "04",
    kicker: "Why us",
    title: "Your junior accountant, in your pocket, powered by Xero",
    points: [
      "Hands you a receipt — it reads it, categorises it, and files it, like an assistant would",
      "Chases who owes you, reconciles the bank, preps your quarterly tax pack — you just ask",
      "We're not replacing your accountant — when you do sit down with one, your books are already audit-ready",
    ],
  },
  {
    n: "05",
    kicker: "Why it's safe to ship",
    title: "Guardrails with real teeth, not just prompts",
    points: [
      "Currency mismatches are refused in code, not just asked about politely",
      "A receipt can't be double-billed — it's marked added the moment it's written",
      "Every write is a real, confirmed Xero action — no shadow ledger, no guesswork",
    ],
    stats: [
      { value: "£0", label: "silent currency conversions" },
      { value: "0", label: "duplicate bills possible" },
      { value: "100%", label: "of writes hit the real Xero API" },
    ],
  },
  {
    n: "06",
    kicker: "Live now",
    title: "Every number you're about to see is real",
    points: [
      "Pulled live from a connected Xero organisation, during this demo",
      "No fixtures, no mockups, no rehearsed data",
      "Nobody opens Xero",
    ],
  },
  {
    n: "07",
    kicker: "Watch it happen",
    title: "Connect your Xero org, then just text your accountant",
    points: [
      "Step 1 — authorise the real Xero OAuth flow, same one Voca uses in production",
      "Step 2 — message the linked WhatsApp number, no app install, no signup form",
      "Step 3 — ask it anything. We'll switch to WhatsApp from here",
    ],
    cta: [
      { label: "Connect Xero", href: `/api/xero/connect?connection_id=${DEMO_CONNECTION_ID}`, primary: true },
      { label: "Text your assistant on WhatsApp", href: WHATSAPP_CONNECT_URL },
    ],
  },
];

export default function LaunchPage() {
  const [i, setI] = useState(0);
  const [dir, setDir] = useState(1);

  function go(next: number) {
    if (next < 0 || next > SLIDES.length - 1) return;
    setDir(next > i ? 1 : -1);
    setI(next);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight" || e.key === " ") go(i + 1);
      if (e.key === "ArrowLeft") go(i - 1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i]);

  const slide = SLIDES[i];

  return (
    <div
      className="min-h-screen w-full relative overflow-hidden flex flex-col justify-between p-10 md:p-20 select-none cursor-pointer"
      style={{ background: "radial-gradient(ellipse at 15% 10%, #0d1620 0%, #070708 55%)" }}
      onClick={() => go(i + 1)}
    >
      {/* giant faded slide number, editorial background watermark */}
      <div
        key={`bg-${i}`}
        className="pointer-events-none absolute -right-10 -top-16 md:-top-24 font-bold leading-none select-none"
        style={{
          fontSize: "min(48vw, 32rem)",
          color: "rgba(19,181,234,0.05)",
          animation: "voca-fade-in 0.5s ease-out",
        }}
      >
        {slide.n}
      </div>

      <div className="flex items-center justify-between text-xs md:text-sm tracking-[0.35em] uppercase text-[#13b5ea] font-mono relative z-10">
        <span>Voca</span>
        <span className="text-[#71717a]">Xero Encode — Bounty 01</span>
      </div>

      <div key={i} className="relative z-10 max-w-5xl" style={{ animation: `voca-slide-${dir > 0 ? "in-right" : "in-left"} 0.4s ease-out` }}>
        <div className="flex items-baseline gap-4 mb-6">
          <span className="text-[#13b5ea]/60 font-mono text-sm md:text-base">{slide.n}</span>
          <span className="text-[#13b5ea] uppercase tracking-[0.25em] text-xs md:text-sm font-mono">
            {slide.kicker}
          </span>
        </div>

        <h1 className="text-3xl md:text-5xl lg:text-6xl font-semibold leading-[1.1] text-[#ededed] max-w-4xl mb-10">
          {slide.title}
        </h1>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-x-8 gap-y-4 mb-10 max-w-4xl">
          {slide.points.map((p, idx) => (
            <div key={p} className="flex gap-3">
              <span className="text-[#13b5ea] font-mono text-sm mt-0.5">{String(idx + 1).padStart(2, "0")}</span>
              <p className="text-sm md:text-base text-[#c4c4c9] leading-relaxed">{p}</p>
            </div>
          ))}
        </div>

        {slide.stats && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 max-w-4xl">
            {slide.stats.map((s) => (
              <div
                key={s.label}
                className="rounded-2xl border border-white/10 bg-gradient-to-b from-white/[0.05] to-transparent p-6 flex flex-col gap-2 backdrop-blur-sm"
              >
                <div className="text-3xl md:text-4xl font-bold text-[#13b5ea] tabular-nums">{s.value}</div>
                <div className="text-xs md:text-sm text-[#8b8b92] leading-snug">{s.label}</div>
              </div>
            ))}
          </div>
        )}

        {slide.cta && (
          <div className="flex flex-col sm:flex-row gap-4 mt-2" onClick={(e) => e.stopPropagation()}>
            {slide.cta.map((c) => (
              <a
                key={c.label}
                href={c.href}
                target={c.href.startsWith("http") ? "_blank" : undefined}
                rel="noreferrer"
                className={
                  c.primary
                    ? "inline-flex items-center justify-center rounded-full bg-[#13b5ea] text-[#070708] font-semibold px-7 py-3.5 text-sm md:text-base hover:bg-[#3fc6f0] transition-colors"
                    : "inline-flex items-center justify-center rounded-full border border-white/20 text-[#ededed] font-semibold px-7 py-3.5 text-sm md:text-base hover:border-white/40 hover:bg-white/5 transition-colors"
                }
              >
                {c.label}
              </a>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between relative z-10">
        <span className="text-xs md:text-sm text-[#71717a] font-mono">
          click / → to advance · ← back
        </span>
        <div className="flex items-center gap-2">
          {SLIDES.map((s, idx) => (
            <div
              key={s.n}
              className="h-1 rounded-full transition-all duration-300"
              style={{
                width: idx === i ? "1.75rem" : "0.4rem",
                background: idx === i ? "#13b5ea" : "rgba(255,255,255,0.15)",
              }}
            />
          ))}
        </div>
      </div>

      <style jsx global>{`
        @keyframes voca-fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes voca-slide-in-right {
          from { opacity: 0; transform: translateX(24px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes voca-slide-in-left {
          from { opacity: 0; transform: translateX(-24px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}
