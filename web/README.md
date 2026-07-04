# Voca Web

Next.js frontend for Voca — connects to the Python backend via the Vercel AI SDK UI message protocol.

## Run

Terminal 1 — Python API:

```bash
cd ..
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Terminal 2 — Next.js:

```bash
cp .env.local.example .env.local
npm run dev
# http://localhost:3000
```

## Features

- `useChat` + `DefaultChatTransport` → proxies to `POST /api/chat` → Python `POST /api/chat`
- **Tool call cards** inline in chat (name, state, input/output JSON)
- **Agent activity** sidebar — live feed of all tool invocations
- **Approve / Reject** for `require_approval` Xero writes (confirm-before-write)

## Stack

- Next.js 16 App Router
- AI SDK v7 (`ai`, `@ai-sdk/react`)
- Tailwind CSS 4
