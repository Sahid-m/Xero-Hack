# Public tunnel (Wassist webhooks)

Wassist needs a **fixed HTTPS URL** for webhooks. Use ngrok with a static domain for local dev.

## Quick start

1. Sign up at [ngrok.com](https://ngrok.com) and claim a free static domain
2. Add to `.env`:

   ```
   NGROK_AUTHTOKEN=...
   NGROK_STATIC_DOMAIN=your-name.ngrok-free.app
   PUBLIC_BASE_URL=https://your-name.ngrok-free.app
   ```

3. Start backend + tunnel:

   ```bash
   uvicorn app.main:app --reload --port 8000
   ngrok http 8000 --domain=your-name.ngrok-free.app
   ```

4. Configure Wassist tools with `https://your-name.ngrok-free.app/whatsapp/webhook`

## Verify

```bash
curl -s https://your-name.ngrok-free.app/health | jq
curl -s https://your-name.ngrok-free.app/whatsapp/webhook
```

GET on `/whatsapp/webhook` returns `{"ok": "true"}` for URL validation.

## Wassist URLs

| Tool | URL |
|------|-----|
| delegate_to_voca | `https://YOUR-DOMAIN/whatsapp/byoa` |
| upload_receipt | `https://YOUR-DOMAIN/whatsapp/receipt` |

## Deploy alternative

For a stable demo without ngrok, deploy the FastAPI backend (Railway, Fly, etc.) and set `PUBLIC_BASE_URL` to the deploy URL.
