#!/usr/bin/env python3
"""Print Xero OAuth consent URL for a session."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from app.config import get_settings
from app.xero_client import authorization_url

load_dotenv()


def main() -> None:
    session_id = sys.argv[1] if len(sys.argv) > 1 else "default"
    settings = get_settings()
    url = authorization_url(session_id, settings)

    print("\n🔐 Xero OAuth\n")
    print(f"Session: {session_id}")
    print("\nOpen this URL in your browser:\n")
    print(url)
    print(
        f"\nOr visit: http://localhost:8000/auth/xero?session_id={session_id}"
    )
    print(
        "\nRegister redirect URI in Xero app: "
        f"{settings.xero_redirect_uri}"
    )


if __name__ == "__main__":
    main()
