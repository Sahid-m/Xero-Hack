# Voca

**"Xero without ever opening Xero"** — voice-first setup & operation agent for the Xero Encode Hackathon (Bounty 01).

Full product spec: [VOCA.md](./VOCA.md)

## Stack

- **Python 3.12+** + FastAPI
- **[Vercel AI SDK for Python](https://github.com/vercel-labs/ai-python)** (`ai`) — agent loop, tools, hooks
- **`/api/chat`** streams the **UI Message protocol** — drop-in compatible with Next.js `useChat`
- **Xero** Custom Connection + `xero-python`
- **ElevenLabs** → `/voice/webhook` (Day 1 PM)

## Quick start

### 1. Xero Custom Connection

1. [developer.xero.com](https://developer.xero.com/app/manage) → **Custom Connection**
2. Scopes: `accounting.settings`, `accounting.contacts`, `accounting.transactions`, `accounting.reports.read`, `offline_access`
3. Connect to **Demo Company** → copy Client ID + Secret

### 2. Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# XERO_CLIENT_ID, XERO_CLIENT_SECRET, ANTHROPIC_API_KEY
```

### 3. Xero auth + verify

```bash
python scripts/xero_auth.py
python scripts/verify_xero.py
```

### 4. Run API

```bash
uvicorn app.main:app --reload --port 8000
# http://localhost:8000/health
# http://localhost:8000/docs
```

### 5. Run Next.js UI

```bash
cd web && cp .env.local.example .env.local && npm install && npm run dev
# http://localhost:3000
```

### 6. Test chat (curl)

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"id":"1","role":"user","parts":[{"type":"text","text":"I run a café"}]}],"session_id":"demo-1"}'
```

## Next.js frontend

See [web/README.md](./web/README.md). The chat UI uses AI SDK `useChat` and shows tool calls inline + in an activity sidebar. Approve/reject buttons wire to Voca's confirm-before-write hooks.

## Architecture

```
Browser → Next.js /api/chat → Python /api/chat → Vercel AI SDK agent → Xero API
Phone → ElevenLabs → (same)
                              ↓
                    data/sessions/ (→ Neon later)
```

## Agent tools

| Phase | Tools |
|-------|-------|
| Setup interview | `configure_business_type`, `configure_vat`, `create_supplier`, `create_customer`, … |
| Daily verbs | `draft_invoice`, `send_invoice`, `get_amount_owed` |

Mutating tools use `require_approval=True` — the agent must get verbal/UI confirmation before Xero writes.

## Environment

| Variable | Purpose |
|----------|---------|
| `XERO_CLIENT_ID` / `XERO_CLIENT_SECRET` | Custom Connection |
| `ANTHROPIC_API_KEY` | Claude via `ai[anthropic]` |
| `AI_DEFAULT_MODEL` | Default `anthropic:claude-sonnet-4-6` |
| `ELEVENLABS_API_KEY` | Voice layer |
