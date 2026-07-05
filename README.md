# Voca

**Xero without ever opening Xero** — WhatsApp bookkeeper for the Xero Encode Hackathon.

Ask on WhatsApp how much you're owed, check your latest invoice, send invoices, chase payments, snap a receipt photo (read by real OCR — not a stub), or reconcile bank transactions against outstanding bills. Voca reads and writes Demo Company (UK) in Xero, and can proactively message you on WhatsApp when something changes in Xero (invoice paid, new bill).

Full product spec: [VOCA.md](./VOCA.md) · Demo script: [DEMO.md](./DEMO.md)

## Stack

| Layer | Tech |
|-------|------|
| API | Python 3.12+, FastAPI, Uvicorn |
| Agent | [Vercel AI SDK for Python](https://github.com/vercel-labs/ai-python) (`ai`) |
| Xero | OAuth + `xero-python` + [Xero hosted MCP](https://builders.xero.com/beta/mcp) |
| WhatsApp | [Wassist BYOA](https://docs.wassist.app/concepts/bring-your-own-agent) |
| Web UI | Next.js 16 (optional — connect Xero + demo mirror) |

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
| Send a receipt photo | Read by a vision model — vendor/amount/category/date extracted for real, currency auto-converted to GBP with a disclosed note |
| `add it` (after a receipt photo) | Records it as a supplier bill in Xero; won't double-add on a stray later "yes" |
| `send invoice to Bayside Club for two hundred pounds plumbing` | Draft + send invoice flow |
| `who should I chase?` | Overdue customers ranked by amount + days late |
| `reconcile my bank transactions with my bills` | Matches unreconciled bank transactions to outstanding invoices/bills by amount/date/contact, then records the payment on confirm |

Voice notes work — Wassist transcribes them to text before calling Voca.

**Proactive notifications:** if you've messaged Voca within the last 24 hours (WhatsApp's customer-service window — there's no true cold-push without a pre-approved template), Voca will follow up on its own when an invoice gets paid or a new bill lands in Xero. Requires a Xero webhook pointed at `/webhooks/xero` — see `XERO_WEBHOOK_KEY` below.

---

## Architecture

```
WhatsApp (text / voice / image)
        ↓
   Wassist BYOA
        ↓
   POST /whatsapp/byoa
        ↓
   Voca (fast Xero lookups + receipt OCR + MCP agent)
        ↓
   Xero Demo Company (UK)
        ↑
   POST /webhooks/xero  ←  Xero (invoice paid / new bill → proactive WhatsApp push)
```

Read-only lookups (owed, latest invoice, cash position) answer **directly in the webhook** (<1s, no LLM
call). Anything slower — the full agent, a receipt photo, invoice writes, reconciliation — **acks
immediately** and delivers the real answer a few seconds later via Wassist's `reply_callback`, so
WhatsApp never sees a stalled request even for multi-step Xero writes.

Web chat (optional):

```
Browser → Next.js → POST /api/chat → Voca agent → Xero
```

---

## Project layout

```
app/
  main.py             FastAPI entrypoint
  wassist.py          WhatsApp BYOA webhook handler (fast paths, async ack+callback, receipts)
  voice_agent.py      WhatsApp turn orchestration
  voice_fast.py       Fast Xero lookups (no LLM): owed, payables, cash, P&L, latest invoice, expenses
  voice_receipt_fast.py  Receipt confirm/add-to-Xero flow (pending-receipt confirmation, dedup)
  receipt_ocr.py      Real receipt OCR via vision model — vendor/amount/category/date extraction
  xero_webhooks.py    Xero webhook receiver — proactive WhatsApp notifications
  agent/              MCP agent + tools (invoices, bills, reconciliation, chase, setup interview)
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
| "Xero isn't connected" | Connect via web UI; set `WASSIST_DEFAULT_CONNECTION_ID` in `.env`; restart API. |
| Wassist never hits webhook | Check `PUBLIC_BASE_URL` matches ngrok domain; ngrok and API both running. |
| Xero webhook never fires | Check the Xero Developer Portal's webhook delivery/notification history for your app — confirms whether Xero even attempted delivery before assuming it's a bug here. |
| Garbled `£` on WhatsApp | Amounts use `GBP 1,234.56` format intentionally. |
| ngrok browser warning | Add header `ngrok-skip-browser-warning: true` for curl tests. |

---

## License

Hackathon project — Xero Encode 2026.
