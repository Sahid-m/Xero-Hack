# Voca

### Xero, run entirely from WhatsApp

**Xero Encode Hackathon — Bounty 01: The Small Business Productivity Powerhouse**

Photograph a receipt and it's read by a vision model, not a canned stub. Ask what you're owed and get
a live number from Xero in under a second. Say "reconcile my bank transactions" and it matches real
bank movement to open invoices, confirms, and closes them out. Ask "am I ready for my MTD update" and
get the exact HMRC quarter, deadline, and a downloadable tax-prep pack mapped to HMRC's own expense
categories. Every one of these is a real Xero API call — nothing here is simulated.

Full product spec: [VOCA.md](./VOCA.md) · Demo script + rehearsal flow: [DEMO.md](./DEMO.md) · Pitch:
[PITCH.md](./PITCH.md)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  WhatsApp                                                                    │
│  text · voice note · receipt photo                                          │
└───────────────────────────────────┬───────────────────────────────────────--┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Wassist (Bring Your Own Agent)                                              │
│  hosts media · transcribes voice notes · proxies WhatsApp Business API      │
└───────────────────────────────────┬───────────────────────────────────────--┘
                                     │ POST /whatsapp/byoa
                                     │ { message, image, phone_number, reply_callback }
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Voca backend  —  Python 3.12 · FastAPI                                     │
│                                                                               │
│  ┌─────────────────┐   ┌───────────────────┐   ┌─────────────────────────┐  │
│  │   Fast paths     │   │   Receipt OCR      │   │   Full agent            │  │
│  │  regex-matched,  │   │  vision model:     │   │  Claude + Xero MCP      │  │
│  │  <1s, no LLM:    │   │  photo → vendor /  │   │  + local write tools:   │  │
│  │  owed / owe /    │   │  amount / category │   │  invoicing, chasing,    │  │
│  │  cash / P&L /    │   │  / date, currency  │   │  reconciliation,        │  │
│  │  latest invoice, │   │  auto-converted    │   │  free-form questions    │  │
│  │  MTD readiness,  │   │  with disclosure   │   │                         │  │
│  │  MTD tax pack    │   │                    │   │                         │  │
│  └────────┬─────────┘   └─────────┬──────────┘   └────────────┬────────────┘  │
│           └───────────────────────┴────────────────────────────┘             │
│                                    │                                          │
│           Slow paths ack in <1s, deliver the real answer a few seconds       │
│           later via reply_callback — WhatsApp never sees a stalled request   │
└────────────────────────────────────┬──────────────────────────────────────--┘
                                     │  xero-python SDK  +  Xero hosted MCP
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Xero Accounting API                                                        │
│  Invoices · Contacts · Payments · BankTransactions · Reports                 │
└───────────────────────────────────┬───────────────────────────────────────--┘
                                     │  Xero webhook (invoice paid / new bill)
                                     ▼
                          POST /webhooks/xero
                                     │
                                     ▼
                proactive WhatsApp follow-up (within the 24h customer-service window)
```

**Optional web UI** (Next.js): `Browser → Next.js → POST /api/chat → Voca agent → Xero` — used to connect
Xero via OAuth and mirror WhatsApp state for a demo dashboard. WhatsApp itself doesn't touch it.

---

## What it does

| Capability | How |
|---|---|
| Live financial Q&A | Instant, cached fast-path answers — no LLM round-trip for common questions |
| Receipt → expense | Vision-model OCR reads vendor/amount/category/date from a photo; converts non-GBP currency with a disclosed rate rather than guessing |
| Invoicing | Draft, authorise, and email a sales invoice in one confirmed step |
| Chasing payment | Ranks overdue customers by amount + days late; emails a reminder via Xero |
| Bank reconciliation | Matches unreconciled bank transactions to outstanding invoices/bills by amount, date, and contact-name similarity; records the payment on confirm |
| MTD tax prep | Maps the current HMRC quarter's Xero data into HMRC's official self-employment expense categories; generates a chart image + CSV/PDF |
| Proactive notifications | A Xero webhook triggers a WhatsApp follow-up when an invoice is paid or a new bill lands |

---

## Prerequisites

- Python 3.12+
- Node.js 20+ (only if running the web UI)
- [Xero developer app](https://developer.xero.com/app/manage) (OAuth web app)
- [Wassist](https://wassist.app) account + API key (WhatsApp)
- [ngrok](https://ngrok.com) static domain (or another HTTPS tunnel) for local WhatsApp webhooks
- Anthropic API key

---

## Quick start

### 1. Clone and install

```bash
cd Fina
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Configure `.env`

Minimum for WhatsApp demo:

```bash
# Xero OAuth
XERO_CLIENT_ID=...
XERO_CLIENT_SECRET=
XERO_REDIRECT_URI=http://localhost:8000/auth/xero/callback

# Claude
ANTHROPIC_API_KEY=...
AI_DEFAULT_MODEL=anthropic:claude-sonnet-4-6
VOICE_AI_MODEL=anthropic:claude-haiku-4-5

# Public URL (ngrok or deploy)
PUBLIC_BASE_URL=https://your-name.ngrok-free.app
NGROK_STATIC_DOMAIN=your-name.ngrok-free.app

# Wassist BYOA
WASSIST_API_KEY=...
WASSIST_API_BASE=https://backend.wassist.app
WASSIST_DEFAULT_CONNECTION_ID=   # set after connecting Xero (step 3)
```

See [.env.example](./.env.example) for all variables.

### 3. Connect Xero (Demo Company)

**Option A — Web UI (easiest)**

```bash
# Terminal 1: API
source .venv/bin/activate
uvicorn app.main:app --port 8000

# Terminal 2: Web
cd web && cp .env.local.example .env.local && npm install && npm run dev
```

Open http://localhost:3000 → **Connect Xero** → sign in to **Demo Company (UK)**.

Copy the `connection_id` from the sidebar (looks like `conv_...`) into `.env`:

```bash
WASSIST_DEFAULT_CONNECTION_ID=conv_your_id_here
```

Restart the API after changing `.env`.

**Option B — CLI**

```bash
source .venv/bin/activate
python scripts/xero_auth.py
python scripts/verify_xero.py
```

### 4. Start the API + ngrok

Use **two terminals**. For WhatsApp demos, run uvicorn **without** `--reload` so background work is not killed mid-request.

```bash
# Terminal 1 — API
source .venv/bin/activate
uvicorn app.main:app --port 8000 --host 127.0.0.1
```

```bash
# Terminal 2 — HTTPS tunnel
ngrok http 8000 --url=your-name.ngrok-free.app
```

Verify:

```bash
curl http://localhost:8000/health
curl https://your-name.ngrok-free.app/health
curl https://your-name.ngrok-free.app/whatsapp/byoa
# {"ok":"true","mode":"byoa"}
```

### 5. Wire up Wassist WhatsApp

Detailed guide: [docs/WASSIST_SETUP.md](./docs/WASSIST_SETUP.md)

Quick version:

```bash
source .venv/bin/activate
python scripts/setup_wassist_byoa.py
```

This registers webhook `https://YOUR-DOMAIN/whatsapp/byoa` and prints a **connectUrl**. Open it on your phone to link WhatsApp.

Or create the agent manually in the [Wassist dashboard](https://wassist.app) → **Agents** → **Bring Your Own Agent** → webhook URL above.

---

## WhatsApp — what to try

| Message | What Voca does |
|---------|----------------|
| `hey` | Greeting + hints |
| `how much am I owed this month?` | Outstanding receivables from Xero |
| `what's my latest invoice I sent?` | Most recent sales invoice |
| `how much do I owe?` | Outstanding bills |
| `what was my recent expense?` | Most recent bill/expense |
| `what's my cash position?` | Receivables + payables + bank activity snapshot |
| `am I ready for my MTD update?` | Current HMRC quarter, submission deadline, income/expenses/net profit so far |
| `prepare my tax pack` | HMRC-category expense breakdown as a chart image + downloadable CSV/PDF |
| Send a receipt photo | Read by a vision model — vendor/amount/category/date extracted for real, currency auto-converted to GBP with a disclosed note |
| `add it` (after a receipt photo) | Records it as a supplier bill in Xero; won't double-add on a stray later "yes" |
| `send invoice to Bayside Club for two hundred pounds plumbing` | Draft + send invoice flow |
| `who should I chase?` | Overdue customers ranked by amount + days late |
| `reconcile my bank transactions with my bills` | Matches unreconciled bank transactions to outstanding invoices/bills by amount/date/contact, then records the payment on confirm |

Voice notes work — Wassist transcribes them to text before calling Voca.

**Proactive notifications:** if you've messaged Voca within the last 24 hours (WhatsApp's customer-service window — there's no true cold-push without a pre-approved template), Voca will follow up on its own when an invoice gets paid or a new bill lands in Xero. Requires a Xero webhook pointed at `/webhooks/xero` — see `XERO_WEBHOOK_KEY` below.

---

## Project layout

```
app/
  main.py             FastAPI entrypoint
  wassist.py          WhatsApp BYOA webhook handler (fast paths, async ack+callback, receipts)
  voice_agent.py      WhatsApp turn orchestration
  voice_fast.py       Fast Xero lookups (no LLM): owed, payables, cash, P&L, latest invoice, expenses, MTD
  voice_receipt_fast.py  Receipt confirm/add-to-Xero flow (pending-receipt confirmation, dedup)
  receipt_ocr.py      Real receipt OCR via vision model — vendor/amount/category/date extraction
  tax_export.py        MTD quarter → HMRC category mapping; CSV/PDF/chart-image rendering
  xero_webhooks.py    Xero webhook receiver — proactive WhatsApp notifications
  agent/              MCP agent + tools (invoices, bills, reconciliation, chase, MTD, setup interview)
web/                  Next.js demo UI + Xero connect
scripts/              Xero auth, Wassist setup, tool tests
docs/WASSIST_SETUP.md
```

---

## Useful commands

```bash
# Health check
curl http://localhost:8000/health

# Test BYOA webhook locally
curl -X POST http://localhost:8000/whatsapp/byoa \
  -H "Content-Type: application/json" \
  -d '{"message":"how much am I owed?","phone_number":"447700900000","image":null,"reply_callback":""}'

# Run tool tests
python scripts/test_voca_tools.py

# API docs
open http://localhost:8000/docs
```

---

## Environment reference

| Variable | Required | Purpose |
|----------|----------|---------|
| `XERO_CLIENT_ID` / `XERO_CLIENT_SECRET` | Yes | Xero OAuth app |
| `XERO_REDIRECT_URI` | Yes | Must match Xero app config (default `http://localhost:8000/auth/xero/callback`) |
| `ANTHROPIC_API_KEY` | Yes | Claude for agent turns |
| `PUBLIC_BASE_URL` | Yes (WhatsApp) | HTTPS URL Wassist calls (ngrok or deploy) |
| `WASSIST_API_KEY` | Yes (WhatsApp) | Wassist → Settings → API Keys |
| `WASSIST_DEFAULT_CONNECTION_ID` | Yes (WhatsApp) | Xero connection id after OAuth — routes all WhatsApp to one org |
| `WASSIST_API_BASE` | No | Default `https://backend.wassist.app` |
| `VOICE_AI_MODEL` | No | Model for WhatsApp turns + receipt OCR (default Haiku) |
| `AI_DEFAULT_MODEL` | No | Model for web chat (default Sonnet) |
| `DATABASE_URL` | No | Postgres/Neon; file storage used if empty |
| `XERO_MCP_URL` | No | Xero hosted MCP endpoint |
| `XERO_WEBHOOK_KEY` | No (proactive notifications) | From Xero Developer Portal → your app → Webhooks, after pointing it at `/webhooks/xero` |

---

## Web UI

See [web/README.md](./web/README.md). The Next.js app is optional for the hackathon demo — use it to connect Xero and mirror WhatsApp state. WhatsApp itself goes through Wassist, not the web UI.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| WhatsApp gets repeated "One sec..." | Restart API **without** `--reload`. The ack text is matched against `_LOOP_PING_MARKERS` in `wassist.py` so Wassist echoing it back as a new inbound message is ignored — if you added new ack wording, add it to that list too. |
| Reply never arrives after "One sec..." | The real answer is delivered async via `reply_callback` a few seconds later — check server logs for `BYOA callback OK` / `failed to POST BYOA reply_callback`. Wassist's callback endpoint occasionally accepts (200) without actually delivering; this is a known Wassist-side reliability gap, not something we can fully control. |
| PDF attachment never arrives on WhatsApp | Confirmed platform limitation on Wassist's shared sandbox WhatsApp number — WhatsApp's document message type is silently dropped there (images deliver fine on the same number). The MTD tax pack sends a chart **image** for this reason; the PDF/CSV are plain download links instead. |
| "Xero isn't connected" | Connect via web UI; set `WASSIST_DEFAULT_CONNECTION_ID` in `.env`; restart API. |
| Wassist never hits webhook | Check `PUBLIC_BASE_URL` matches ngrok domain; ngrok and API both running. |
| Xero webhook never fires | Check the Xero Developer Portal's webhook delivery/notification history for your app — confirms whether Xero even attempted delivery before assuming it's a bug here. |
| Garbled `£` on WhatsApp | Amounts use `GBP 1,234.56` format intentionally. |
| ngrok browser warning | Add header `ngrok-skip-browser-warning: true` for curl tests. |

---

## Production readiness

Built for a hackathon demo on a single connected Xero org — honest about the gap between that and a
real multi-tenant product:

**Solid / demo-tested:**
- Every read and write is a real Xero Accounting API call, verified against a live org throughout development
- Receipt OCR, reconciliation matching, and MTD category mapping all tested against real Xero data, not fixtures
- Async ack+callback pattern means slow multi-step Xero writes don't stall the WhatsApp webhook
- Guardrails with real teeth: duplicate-receipt protection, contact-matching that refuses to misattribute to an unrelated existing contact, confidence-gated reconciliation matches

**Known gaps before this could run for real users:**
- **Single-tenant routing** — all WhatsApp traffic routes to one hardcoded `WASSIST_DEFAULT_CONNECTION_ID`; a real product needs per-user phone → Xero-org mapping (the plumbing exists via `link_whatsapp_phone`, just not the onboarding flow around it)
- **Confirm-before-write is prompt-level, not fully hard-enforced** — `require_approval` hooks are auto-granted for WhatsApp/voice turns (no interactive UI to pause on), so the model's own judgment does the confirming; the currency-mismatch guardrail was moved to a real code-level check after live testing caught it failing, but not every write path has an equivalent hard gate yet
- **WhatsApp number is Wassist's shared sandbox** — a verified production WhatsApp Business number is needed for reliable document delivery and to remove sandbox-tier restrictions
- **MTD tax pack is preparation, not filing** — actual HMRC submission requires formal HMRC software-vendor accreditation and a direct API connection to HMRC's MTD service, well beyond hackathon scope
- **No automated test suite** beyond `scripts/test_voca_tools.py` — correctness here was established via live testing against the connected Xero org during development, not CI-gated regression tests

---

## Checkpoint 2 Submission

Answers ready to paste into the submission form.

### Detailed explanation of your submission

Voca is a WhatsApp-native AI bookkeeping assistant for UK sole traders and small businesses, built on
the Xero API for the "Small Business Productivity Powerhouse" bounty. It closes the receipt → expense
→ reconciliation → reporting loop the bounty describes, entirely through a WhatsApp conversation: a
user photographs a receipt, which is read by a vision-model OCR (not a canned demo) for vendor,
amount, category, and date, converting non-GBP currency with a disclosed rate rather than guessing;
confirms to record it as a Xero bill; asks Voca to reconcile bank transactions, which cross-references
unreconciled bank movement against outstanding invoices/bills by amount, date proximity, and
contact-name similarity, then records a real Xero payment on confirmation; asks live financial
questions (amount owed, cash position, latest invoice) answered instantly from Xero; sends and chases
invoices; and generates a Making Tax Digital quarterly tax-prep pack mapping real Xero data into
HMRC's own official self-employment expense categories, delivered as a chart image and downloadable
CSV/PDF. A Xero webhook also drives proactive WhatsApp follow-ups when an invoice is paid or a new
bill lands. Every read and write in the conversation is a live Xero API call — nothing is simulated
locally.

### How did your project utilize the Xero API?

The core workflow is an AI agent (Claude, via the Vercel AI SDK for Python) given both Xero's own
hosted MCP server and a set of local Python tools calling the Xero Accounting API directly (via the
`xero-python` SDK) for actions the MCP server doesn't cover — authorising and emailing invoices,
recording supplier bills, recording reconciliation payments, and Making Tax Digital reporting. Every
financial answer or action in the WhatsApp conversation — checking balances, reading invoices/bills,
creating and sending invoices, recording bills from OCR'd receipts, matching and recording
reconciliation payments, pulling P&L for tax reporting — is backed by a live call to the Xero
Accounting API against the connected Xero organisation.

### Which specific Xero API endpoints did your application interact with?

| Endpoint | Method(s) |
|---|---|
| `/Organisation` | GET |
| `/Contacts`, `/Contacts/{ContactID}` | GET, POST |
| `/Invoices`, `/Invoices/{InvoiceID}` | GET, POST (create + update/authorise) |
| `/Payments` | GET, POST |
| `/BankTransactions`, `/BankTransactions/{BankTransactionID}` | GET |
| `/Accounts` | GET |
| `/TaxRates` | GET |
| `/TrackingCategories` | GET |
| `/BrandingThemes` | GET |
| `/Items` | GET |
| `/Reports/ProfitAndLoss` | GET |
| `/Reports/AgedReceivablesByContact`, `/Reports/AgedPayablesByContact` | GET |
| `identity.xero.com/connect/token` | POST (OAuth 2.0 code exchange + refresh) |
| `api.xero.com/connections` | GET (tenant discovery post-OAuth) |
| Xero hosted MCP server (`builders.xero.com/beta/mcp`) | wraps the same Invoices/Contacts/Reports endpoints for the agent's dynamic tool-calling |
| Xero Webhooks (Invoices topic) | inbound — Xero calls our `POST /webhooks/xero` on invoice create/update events |

### What development platform did you use?

Python 3.12 + FastAPI backend; Anthropic Claude (Sonnet for the full agent, Haiku for WhatsApp turns
and receipt OCR) via the [Vercel AI SDK for Python](https://github.com/vercel-labs/ai-python), combined
with Xero's hosted MCP server for live tool-calling; Next.js 16 for the optional web UI; PostgreSQL
(Neon) for session/token storage; [Wassist](https://wassist.app) (Bring Your Own Agent) for WhatsApp
delivery; ngrok for the local HTTPS tunnel; Pillow and fpdf2 for chart/PDF generation.

### Link to Presentation

_[add link here before submitting]_

### What Xero OAuth 2.0 scopes did your application require?

```
openid
profile
email
offline_access
accounting.settings
accounting.contacts
accounting.invoices
accounting.payments
accounting.banktransactions
accounting.attachments
accounting.reports.aged.read
accounting.reports.profitandloss.read
```

### Submission files

- Demo recording (see [DEMO.md](./DEMO.md) for the rehearsed script)
- [PITCH.md](./PITCH.md) — pitch deck content / talking points
- This repository

---

## License

Hackathon project — Xero Encode 2026.
