#!/usr/bin/env bash
# Start a stable HTTPS tunnel to the Voca backend (port 8000).
#
# Recommended: ngrok with a FREE static domain (URL never changes).
#   1. Sign up: https://dashboard.ngrok.com/signup
#   2. Copy authtoken → NGROK_AUTHTOKEN in .env
#   3. Cloud Edge → Domains → create free *.ngrok-free.app domain
#   4. Set NGROK_STATIC_DOMAIN=voca-demo.ngrok-free.app in .env
#   5. Run: ./scripts/start_tunnel.sh
#
# Then set PUBLIC_BASE_URL in .env to the same domain and restart uvicorn.

set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"

# Load .env if present
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if command -v ngrok >/dev/null 2>&1; then
  if [[ -n "${NGROK_AUTHTOKEN:-}" ]]; then
    ngrok config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null 2>&1 || true
  fi

  if [[ -n "${NGROK_STATIC_DOMAIN:-}" ]]; then
    echo "Starting ngrok → https://${NGROK_STATIC_DOMAIN} → localhost:${PORT}"
    echo ""
    echo "Set in .env:"
    echo "  PUBLIC_BASE_URL=https://${NGROK_STATIC_DOMAIN}"
    echo ""
    exec ngrok http "$PORT" --domain="$NGROK_STATIC_DOMAIN"
  fi

  echo "Starting ngrok (random URL — set NGROK_STATIC_DOMAIN in .env for a fixed URL)"
  exec ngrok http "$PORT"
fi

if command -v cloudflared >/dev/null 2>&1 && [[ -n "${CLOUDFLARE_TUNNEL_NAME:-}" ]]; then
  echo "Starting Cloudflare named tunnel: ${CLOUDFLARE_TUNNEL_NAME}"
  exec cloudflared tunnel run "$CLOUDFLARE_TUNNEL_NAME"
fi

echo "No stable tunnel tool found."
echo ""
echo "Install ngrok (recommended):"
echo "  brew install ngrok/ngrok/ngrok"
echo "  # or download from https://ngrok.com/download"
echo ""
echo "Then add to .env:"
echo "  NGROK_AUTHTOKEN=..."
echo "  NGROK_STATIC_DOMAIN=your-name.ngrok-free.app"
echo "  PUBLIC_BASE_URL=https://your-name.ngrok-free.app"
exit 1
