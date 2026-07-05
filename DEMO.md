# Voca — Demo playbook

**"Xero, run entirely from WhatsApp"** — for the Xero Encode Hackathon, Bounty 01: *The Small Business
Productivity Powerhouse*.

---

## The pitch (30 seconds)

> *"A sole trader's books live in three places: a shoebox of receipts, a banking app, and Xero — which they
> open maybe once a month, confused. Voca collapses all three into one WhatsApp thread. Photograph a
> receipt, it's read and categorised. Ask what you're owed, it's live from Xero. Say 'reconcile my bank
> transactions,' it matches payments to bills and closes them out. No app to learn, no login, no UI —
> just the app they already have open all day."*

**Why Xero is central, not an add-on:** every step — OCR extraction, invoicing, chasing payments,
reconciliation — reads and writes real Xero data through the API. Nothing is simulated locally; the
WhatsApp thread is a control surface, Xero is the ledger of record.

---

## Architecture (one breath)

```
WhatsApp (photo / text / voice note)
        │
        ▼
   Wassist (BYOA webhook) — hosts media, transcribes voice notes
        │  POST /whatsapp/byoa  { message, image, phone_number, reply_callback }
        ▼
   Voca backend (FastAPI)
        │
        ├─ Fast paths (regex-matched, <1s): receivables, payables, cash position,
        │  P&L, latest invoice, recent expense, receipt confirm/add, MTD readiness,
        │  MTD tax pack (chart + CSV/PDF)
        │
        ├─ Receipt OCR (vision model): photo → vendor / amount / category / date,
        │  auto-converts non-GBP currency with a disclosed note
        │
        └─ Full agent (Claude + Xero MCP + local tools): anything else —
           invoicing, chasing, reconciliation, free-form questions
                │
                ▼
        Xero (Demo Company) — contacts, invoices, bills, bank transactions, payments
                ▲
                │ Xero webhook (invoice paid / new bill)
        POST /webhooks/xero → proactive WhatsApp follow-up (within 24h window)
```

Slow paths (full agent, OCR+write combos) **ack immediately** and deliver the real answer via
`reply_callback` a few seconds later — so WhatsApp never sees a stalled webhook, even for multi-step
Xero writes.

---

## Live demo data (verify before stage — these are real, pulled live)

| Fact | Value |
|------|-------|
| **Total owed to you** | **£23,144.38** across **29** unpaid invoices |
| **Top debtor** | Ridgeway University — **£6,187.50** |
| **Total you owe suppliers** | **£10,645.40** across **25** unpaid bills |

Numbers drift as the demo runs (that's the point — it's live). Refresh with *"how much am I owed"*
just before judges arrive.

---

## The workflow that answers the bounty: receipt → expense → reconciliation → reporting

This is the core script. Each step is a real WhatsApp message; each response is a real Xero write.

### Step 1 — Receipt → expense (OCR)

**Send a photo** of any receipt (a real one, or use a sample — a US repair-shop receipt works well
because it forces the currency-safety behaviour below) with the caption:

> *"Here's my receipt"*

**Expect:**
> *Got it — [Vendor], £[amount], [category]. Say add that to Xero when you're ready. (Original amount
> $X USD converted to GBP at approximate rate of Y...)*

Point out live: vendor, amount, and category were **read from the photo**, not typed — and if the
receipt is in a foreign currency, it's converted and the conversion is disclosed, not silently guessed.

### Step 2 — Confirm → bill recorded

> *"Add it"*

**Expect:**
> *Recorded bill [ref] from [Vendor] for £[amount] - [category].*

Flip to Xero → **Business → Bills to pay** on the projector: the bill is really there, correct amount,
correct supplier (created fresh if new — matched safely, never misattributed to an unrelated existing
contact with a similar name).

### Step 3 — Reconciliation (the bounty's "smart matching")

**⚠️ Needs a fresh unreconciled pair before each rehearsal/take** — once a match is reconciled, it's
gone (real Xero data, not reset between runs). Either: (a) create a bill via the receipt-photo flow
above, then get a matching bank transaction recorded against the same supplier/amount (in Xero
directly, or ask me to seed one — that's a real write to your live org, so I'll always ask first), or
(b) check `find_reconciliation_matches` a beat before recording to confirm a live pair currently
exists.

> *"Can you reconcile my bank transactions with my bills please"*

**Expect:** Voca cross-references unreconciled bank transactions against outstanding bills/invoices by
amount, date proximity, and contact-name similarity, and proposes a ranked match:

> *[Supplier] — bank payment £X on [date] matches invoice [ref] for £X ([description]). N% confidence.
> Should I reconcile this?*

> *"Yes please reconcile it"*

**Expect:**
> *Done. Reconciled — matched £X bank transaction to invoice [ref] ([supplier]). Both are now settled.*

Flip to Xero → the bill now shows **Paid**, and a Payment record links it to the bank transaction.
This is the step most bookkeeping tools *don't* automate — matching real bank movement to the right
open invoice/bill without a human squinting at two screens.

### Step 4 — Reporting and the actual regulatory deadline

> *"What's my cash position?"*

**Expect (instant, fast-path):**
> *You're owed £X and you owe £Y to suppliers. There were N bank transactions in the last seven days.*

Then the closer — the question that actually matters given Making Tax Digital:

> *"Am I ready for my MTD update?"*

**Expect (instant, fast-path):**
> *MTD Q1 (2026-04-06 to 2026-07-05): £X income, £Y expenses, £Z net profit so far. Next digital
> update due 2026-08-07 - N days away.*

This is computed live — which HMRC quarter today falls in, the exact submission deadline, and the
real income/expenses/net profit that quarter's digital update will be built from.

### Step 5 — The tax pack (turns numbers into a filing-ready artefact)

> *"Prepare my tax pack"*

**Expect (instant, fast-path):** turnover and expenses mapped into HMRC's actual official
self-employment expense categories, plus a chart image and CSV/PDF download links — a real bar chart
of the category breakdown arrives as a WhatsApp image a few seconds later (fire-and-forget, doesn't
block the text reply). Always framed honestly: **this preps the numbers, it is not itself a submission
to HMRC** (real MTD filing needs HMRC-accredited software talking to their API directly).

**One line closing the loop:** *"Photo in, bill recorded, payment matched, tax pack ready — nobody
opened Xero, and every number came from the real API."*

---

## Supporting paths (use if time allows / judges ask)

### Invoicing a customer

> *"Send an invoice to Bayside Club for two hundred pounds for plumbing — yes go ahead"*

Creates, authorises, and emails the invoice in one shot.

**Do not demo the currency-mismatch guardrail live right now.** It's enforced in code at the tool
level (`draft_invoice`/`create_and_send_invoice` refuse a non-GBP `currency` argument), but a known gap
remains: the invoice *fast path*'s number parser (`parse_gbp`) ignores currency words entirely when a
number-word phrase like "two hundred" is present, so "two hundred dollars" can still slip through the
fast path and create a GBP invoice before the tool-level guardrail ever sees it. Confirmed live during
testing — do not repeat this phrase on stage until that fast-path gap is closed.

### Chasing overdue payment

> *"Who should I chase?"* → ranked list by amount + days overdue
> *"Send a payment reminder to [customer]"* → emails a chase via Xero

### Everyday questions (all instant, fast-path, no LLM round-trip)

- *"How much am I owed?"*
- *"What do I owe suppliers?"*
- *"What's my latest invoice?"*
- *"What was my recent expense?"*
- *"What's my cash position?"*
- *"Am I ready for my MTD update?"*
- *"Prepare my tax pack"*

---

## Why this wins the "reliable, easy to adopt, time-saving" bar

| Bounty criterion | How Voca hits it |
|---|---|
| **Reliable and accurate** | Confirm-before-write on every financial action; currency-mismatch guardrail; contact-matching only creates a new supplier/customer when no real match exists (no silent misattribution); duplicate-add protection on receipts |
| **Easy to adopt (non-technical)** | Zero UI to learn — WhatsApp is already open all day. No login beyond one-time Xero OAuth |
| **Time-saving, impactful** | Receipt-to-bill in two messages; reconciliation that would take minutes of screen-squinting done in one confirm; live figures without opening Xero at all |
| **Xero central, not an add-on** | Every read and write is a real Xero API call — OCR output, invoices, bills, payments, bank transactions all live in the org, nothing simulated |
| **Beyond simple rules** | Vision-based OCR handles messy real receipts (wrong currency, mislabelled contents); fuzzy contact matching with safety rails; confidence-scored reconciliation matching, not exact-string rules |

---

## Judge Q&A

| Question | Answer |
|---|---|
| *"Isn't this just the official Xero MCP connector?"* | MCP is the plumbing — it lets an LLM call Xero's API. Voca is the workflow on top: WhatsApp delivery (no setup, no desktop app), OCR that turns a photo into a bill, currency-safety and duplicate-add guardrails, and reconciliation matching that MCP alone doesn't give you. MCP answers "how do I connect an AI to Xero"; Voca answers "how does a plumber turn a receipt into a reconciled expense from a van." |
| *"What if OCR misreads the receipt?"* | It always confirms before writing anything, and discloses uncertainty (e.g. "this doesn't look like a fuel receipt, may not be suitable for a UK expense claim") rather than silently guessing. |
| *"What stops it double-billing?"* | A receipt is marked "added" after the write; a stray later "yes" won't re-record it. |
| *"Reconciliation sounds risky — what if it matches wrong?"* | It only acts after an explicit confirm, and only surfaces matches above a confidence threshold (amount + date + contact-name similarity) — low-confidence pairs are never proposed. |
| *"Business model?"* | Undercuts a £100–200/month bookkeeper; every write is Xero-native so accountants get clean data, not a shadow ledger. |
| *"Does it just answer questions, or actually help file taxes?"* | It maps the quarter's real Xero data into HMRC's own official expense categories and hands you a chart + CSV/PDF — genuine prep work, not just a chat answer. Framed honestly: it's not a submission (that needs HMRC-accredited software talking to their API directly), it's the "raw Xero export → HMRC categories" step done for you. |
| *"Can it message you proactively, not just reply?"* | Yes — a Xero webhook triggers a WhatsApp follow-up when an invoice gets paid or a new bill lands, within WhatsApp's 24h customer-service window (no cold-push without a pre-approved template, a real platform constraint, not a shortcut we took). |

---

## Pre-demo checklist

- [ ] Backend running: `uvicorn app.main:app --port 8000 --host 127.0.0.1` (no `--reload` — avoids
      mid-demo restarts dropping in-flight WhatsApp state)
- [ ] Tunnel live: `./scripts/start_tunnel.sh` → confirm `PUBLIC_BASE_URL` matches your Wassist BYOA
      webhook config
- [ ] `curl $PUBLIC_BASE_URL/health` → `ok: true`
- [ ] Xero connected for the demo `connection_id` (web app → Connect Xero)
- [ ] Run *"how much am I owed"* once before judges arrive — refreshes the fast-path cache and confirms
      the whole chain works
- [ ] **Confirm a fresh reconciliation match exists** (Step 3 above) — it's consumed once used and
      doesn't reset
- [ ] **Do not** demo "two hundred dollars" style currency phrasing — known fast-path gap, see Step 4
      area above
- [ ] If demoing proactive notifications: confirm the Xero webhook is registered (developer.xero.com →
      your app → Webhooks → `/webhooks/xero`) and you've messaged Voca within the last 24h
- [ ] Have a receipt photo ready to send (camera roll or a saved sample image)
- [ ] Projector on Xero: **Bills to pay** and **Sales overview** tabs ready to flip to
- [ ] Backup: screen-record one full clean run beforehand in case of live-demo gremlins

## If something breaks

| Problem | Recovery |
|---|---|
| WhatsApp reply never arrives | Check `/health` on the tunnel URL; fall back to curling `/whatsapp/byoa` directly on stage to show the API still works |
| OCR gives an odd read | That's honest behaviour, not a crash — call it out ("see, it tells us when it's unsure") and move to the pre-recorded backup for that step |
| Reconciliation finds no match | Numbers drift as the demo runs — ask *"what's my cash position"* instead, or reference the recorded backup |
| Total meltdown | Play the backup video |
