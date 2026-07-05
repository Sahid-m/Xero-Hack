# Wassist WhatsApp setup (BYOA — recommended)

Voca uses **Wassist Bring Your Own Agent (BYOA)** — Wassist handles WhatsApp; Voca is the brain.

Docs: [Bring Your Own Agent](https://docs.wassist.app/concepts/bring-your-own-agent)

## Architecture

```
WhatsApp (text / voice note / image)
        ↓
   Wassist (transcribes voice notes, hosts media)
        ↓
   POST /whatsapp/byoa
   { message, image, phone_number, reply_callback }
        ↓
   Voca (fast Xero lookups + MCP agent) → { "content": "..." }
        ↓
   Wassist delivers reply on WhatsApp
```

Voca answers **in the webhook response** (sync). Wassist `reply_callback` is not used — it caused retry loops in practice.

---

## Step 1 — Backend + tunnel

`.env`:

```bash
ANTHROPIC_API_KEY=...
XERO_CLIENT_ID=...
XERO_CLIENT_SECRET=...
PUBLIC_BASE_URL=https://your-name.ngrok-free.app

# Wassist BYOA (Settings → API Keys at wassist.app)
WASSIST_API_KEY=...
WASSIST_API_BASE=https://backend.wassist.app

# Optional: skip phone linking for solo demo
WASSIST_DEFAULT_CONNECTION_ID=conv_xxx
```

Start (use **two terminals** — no `--reload` for WhatsApp demos):

```bash
# Terminal 1
uvicorn app.main:app --port 8000 --host 127.0.0.1

# Terminal 2
ngrok http 8000 --url=your-name.ngrok-free.app
```

Verify:

```bash
curl https://your-name.ngrok-free.app/whatsapp/byoa
# {"ok":"true","mode":"byoa"}
```

---

## Step 2 — Connect Xero

1. Open Voca web app → **Connect Xero**
2. Copy `connection_id` from sidebar (or localStorage `voca_connection_id`)
3. Either:
   - Set `WASSIST_DEFAULT_CONNECTION_ID=conv_xxx` in `.env`, **or**
   - Link your WhatsApp number (Step 4)

---

## Step 3 — Create BYOA agent (API — easiest)

```bash
python scripts/setup_wassist_byoa.py
```

This calls `POST /api/v1/agents/byoa/` with your webhook URL:

`https://YOUR-DOMAIN/whatsapp/byoa`

The script prints a **`connectUrl`** — open it to test in Wassist's sandbox WhatsApp.

### Or create in the dashboard

1. [wassist.app](https://wassist.app) → **Agents** → **Create Agent**
2. Choose **Bring Your Own Agent**
3. Webhook URL: `https://YOUR-DOMAIN/whatsapp/byoa`
4. Save and deploy

---

## Step 4 — Link your WhatsApp number (optional)

If you don't use `WASSIST_DEFAULT_CONNECTION_ID`, link your number so BYOA knows which Xero org to use:

```bash
curl -X POST http://localhost:8000/api/whatsapp/link \
  -H "Content-Type: application/json" \
  -d '{"connection_id":"YOUR_CONNECTION_ID","phone_number":"+447700900123"}'
```

Use the same number you message from on WhatsApp.

---

## Step 5 — Test

### curl (BYOA format)

```bash
curl -X POST "$PUBLIC_BASE_URL/whatsapp/byoa" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How much am I owed?",
    "phone_number": "+447700900123",
    "image": null,
    "reply_callback": ""
  }'
```

Response:

```json
{
  "content": "You're owed GBP 22,944.38 across 28 unpaid invoices..."
}
```

Lookups may take 5–15 seconds while Xero is queried.

### Voice note

Wassist transcribes audio → sends as `message`. Voca processes it the same as text (may take longer for invoice writes).

### Receipt photo

Send an image on WhatsApp — BYOA includes `"image": "https://media.wassist.app/..."`:

Voca stores the demo Shell receipt stub and replies with amount + vendor.

---

## Demo script

1. **Photo** — Shell receipt → *"Got it — Shell, £47.50…"*
2. **Voice note** — *"Add that to Xero"*
3. **Voice note** — *"How much am I owed?"*
4. **Text** — *"Send invoice to Bayside Club £200 plumbing"*
5. **Mirror** — `/demo` for judges

---

## Endpoints

| Route | Purpose |
|-------|---------|
| `GET/POST /whatsapp/byoa` | **BYOA webhook** (use this) |
| `POST /api/whatsapp/link` | Link phone → connection_id |
| `GET/POST /whatsapp/webhook` | Legacy custom API tool |
| `GET /api/demo/state` | Mirror dashboard |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| API 404 on agent create | Try `WASSIST_API_BASE=https://wassist.app` |
| No Xero access | Connect Xero + set `WASSIST_DEFAULT_CONNECTION_ID` |
| Voice notes not working | Wassist must transcribe → `message` field |
| Repeated "One sec..." loop | Restart API without `--reload`; pull latest code |
| Invoice writes slow | Normal — full agent may take 20–30s in one reply |

See also: [docs/TUNNEL.md](./TUNNEL.md)
