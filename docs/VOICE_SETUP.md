# Voca Phone — ElevenLabs Setup

**Architecture in one line:** ElevenLabs handles the phone call and natural conversation. **One webhook** sends each instruction to Voca. Voca runs the full Xero agent (all tools) and returns text for ElevenLabs to speak.

```
Caller  →  Twilio number  →  ElevenLabs Agent (voice + small talk)
                                    │
                                    │  webhook: delegate_to_voca
                                    │  { task, caller_phone, connection_id }
                                    ▼
                            Voca Python backend
                            (Claude + all Xero tools)
                                    │
                                    │  { result: "You're owed £20,441..." }
                                    ▼
                            ElevenLabs speaks it to caller
```

ElevenLabs does **not** need separate tools per Xero action. It passes the caller's instruction in plain English; Voca decides which tools to call.

---

## Prerequisites

- Voca backend running and reachable on HTTPS (`PUBLIC_BASE_URL`)
- Xero OAuth working in the web app
- [ElevenLabs](https://elevenlabs.io) account (Agents / Conversational AI)
- [Twilio](https://twilio.com) account with a voice-capable phone number

### `.env` on the backend

```bash
ELEVENLABS_API_KEY=sk_...
ELEVENLABS_AGENT_ID=          # fill after creating the agent
VOCA_PHONE_NUMBER=+447...     # your Twilio number (display + init)
PUBLIC_BASE_URL=https://xxxx.ngrok-free.app   # or your deployed URL
```

Expose port 8000:

```bash
ngrok http 8000
# copy https URL → PUBLIC_BASE_URL
```

---

## Step 1 — Twilio phone number

1. Twilio Console → **Phone Numbers** → **Buy a number** (voice enabled).
2. Note the number in E.164 form, e.g. `+447700900123`.
3. Set `VOCA_PHONE_NUMBER` in `.env`.

You do **not** need to hand-configure Twilio webhooks if you use ElevenLabs native import (Step 4).

---

## Step 2 — Create the ElevenLabs agent

1. Go to [elevenlabs.io](https://elevenlabs.io) → **Agents** (or Conversational AI).
2. **Create agent** → name it **Voca**.
3. **Voice** — pick a clear UK-friendly voice (e.g. Rachel, George).
4. **Language** — English.

### System prompt (paste this)

```
You are Voca on a live phone call — a warm, efficient UK bookkeeper.

YOUR JOB IS CONVERSATION ONLY. You do not know any figures from Xero yourself.

For EVERY request about their books (amounts owed, invoices, bills, contacts, profit and loss, setup):
→ Call the tool `delegate_to_voca` with:
  - task: the caller's full request in plain English (include names, amounts, dates they mention)
  - caller_phone: {{caller_phone}}
  - connection_id: {{connection_id}}

Examples of task strings:
- "How much am I owed right now?"
- "Draft an invoice for the Hendersons, two hours at 45 pounds plus 40 pounds parts"
- "List my unpaid bills"
- "What was profit and loss this month?"

Rules:
- Keep your own speech short (2–4 sentences) unless reading back tool results.
- Read tool results naturally — no markdown, no tables.
- Confirm before sending invoices or creating contacts: "Shall I go ahead and send that?"
- If xero_linked is false, tell them to connect Xero in the Voca web app first.
- Never invent numbers — always use the tool.
```

### First message

```
Hi, it's Voca — your Xero bookkeeper. What can I do for you today?
```

(The `/voice/init` webhook will override this per caller when they ring.)

---

## Step 3 — Add the server tool (single webhook)

In the agent → **Tools** → **Add tool** → **Webhook**:

| Field | Value |
|--------|--------|
| **Name** | `delegate_to_voca` |
| **Description** | Send any accounting instruction to Voca. Queries and changes in Xero. Always use for book-related requests. |
| **URL** | `https://YOUR-PUBLIC-URL/voice/tools/delegate` |
| **Method** | `POST` |

### Request body (JSON schema)

```json
{
  "type": "object",
  "properties": {
    "task": {
      "type": "string",
      "description": "Full instruction from the caller in plain English"
    },
    "caller_phone": {
      "type": "string",
      "description": "Always pass {{caller_phone}}"
    },
    "connection_id": {
      "type": "string",
      "description": "Always pass {{connection_id}}"
    }
  },
  "required": ["task"]
}
```

ElevenLabs will POST:

```json
{
  "tool_call_id": "call_abc",
  "tool_name": "delegate_to_voca",
  "parameters": {
    "task": "How much am I owed?",
    "caller_phone": "+447700900123",
    "connection_id": "uuid-here"
  },
  "conversation_id": "conv_xyz"
}
```

Voca responds:

```json
{
  "result": "You're owed twenty thousand four hundred and forty one pounds across fourteen invoices."
}
```

ElevenLabs speaks `result` to the caller.

Run `python scripts/setup_elevenlabs_phone.py` to print the tool JSON with your URL filled in.

---

## Step 4 — Conversation initiation webhook (inbound calls)

This links the caller's phone → their Xero account before the agent speaks.

1. Agent → **Security** or **Webhooks** → **Conversation initiation**.
2. Enable **Fetch conversation initiation data** for inbound Twilio calls.
3. URL: `https://YOUR-PUBLIC-URL/voice/init`
4. Method: `POST`

On each inbound call, Voca returns:

- `dynamic_variables`: `caller_phone`, `connection_id`, `xero_linked`
- personalised `first_message` (connected vs not linked)

In the agent prompt, use `{{caller_phone}}`, `{{connection_id}}`, `{{xero_linked}}` in the tool call.

---

## Step 5 — Import Twilio number into ElevenLabs

1. ElevenLabs → **Phone numbers** → **Import**.
2. Choose **Twilio**.
3. Enter Twilio **Account SID** + **Auth Token**.
4. Select your number.
5. **Assign** the Voca agent to that number.

ElevenLabs configures Twilio voice webhooks automatically.

Copy **Agent ID** → `ELEVENLABS_AGENT_ID` in `.env`.

---

## Step 6 — Link caller phone in Voca web app

1. Open `http://localhost:3000` (or your deployed UI).
2. **Connect Xero**.
3. Sidebar → **Call your bookkeeper** → enter your mobile → **Link**.

When you call from that number, `/voice/init` resolves your Xero connection.

---

## Step 7 — Test

### Test the backend directly

```bash
curl -X POST https://YOUR-PUBLIC-URL/voice/tools/delegate \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "delegate_to_voca",
    "parameters": {
      "task": "How much am I owed?",
      "caller_phone": "+447700900123",
      "connection_id": "YOUR-CONNECTION-UUID"
    }
  }'
```

### Test a live call

1. Call your Twilio number from the linked mobile.
2. Say: *"How much am I owed right now?"*
3. You should hear Voca read live figures from Xero.

### Test from ElevenLabs dashboard

Phone numbers → your number → **Outbound test call** (optional).

---

## What Voca does with each instruction

The `task` string is passed to the **same agent** as the web chat:

- All read tools (invoices, P&L, contacts, amounts owed, …)
- Write tools (draft/send invoice, create contacts) — confirmed verbally on the call
- Setup interview if they ask to get set up

Voice replies are shortened for speech (no markdown tables).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "I don't have your number on file" | Link mobile in web app sidebar |
| "Xero isn't connected" | Connect Xero in web app, same browser session / connection id |
| Tool never called | Strengthen prompt: "ALWAYS call delegate_to_voca for book questions" |
| Webhook timeout | Use ngrok/deploy closer region; Voca target &lt; 15s for simple queries |
| `Load failed` on web | Separate issue — phone uses `/voice/tools/delegate`, not web chat |

---

## API reference

| Endpoint | Purpose |
|----------|---------|
| `POST /voice/init` | ElevenLabs inbound call — caller lookup + greeting |
| `POST /voice/tools/delegate` | **Main tool** — run Voca agent on `task` |
| `POST /voice/instruct` | Same as delegate (simpler body shape) |
| `GET /voice/status` | Phone configured? Webhook URLs |
| `POST /api/voice/link` | Link phone → connection id |
