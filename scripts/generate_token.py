#!/usr/bin/env python3
"""Generate JWT tokens for Matilda transcription service clients.

Usage:
    python scripts/generate_token.py <client_name> [--days DAYS]

Examples:
    python scripts/generate_token.py "Johns iPhone"
    python scripts/generate_token.py "Mobile App" --days 90
    python scripts/generate_token.py "Test Client" --days 7

"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from matilda_ears.core.config import get_config
from matilda_ears.core.token_manager import TokenManager


def main():
    parser = argparse.ArgumentParser(description="Generate JWT tokens for STT transcription service clients")
    parser.add_argument("client_name", help="Name/identifier for the client (e.g., 'Johns iPhone', 'Mobile App')")
    parser.add_argument("--days", type=int, default=30, help="Token expiration in days (default: 30)")
    parser.add_argument("--one-time", action="store_true", help="Generate a one-time-use token")
    parser.add_argument(
        "--show-full-token", action="store_true", help="Display the full token (security risk - use with caution)"
    )

    args = parser.parse_args()

    # Get config and token manager
    config = get_config()
    token_manager = TokenManager(config.jwt_secret_key)

    # Generate token
    token_data = token_manager.generate_token(
        client_name=args.client_name,
        expiration_days=args.days,
        one_time_use=args.one_time,
    )
    token = token_data["token"]

    print(f"✅ Generated JWT token for '{args.client_name}' (expires in {args.days} days)")

    if args.show_full_token:
        print("\n🔑 Full Token:")
        print(f"{token}")
        print("\n📋 Example usage in WebSocket messages:")
        print('{ "type": "auth", "token": "YOUR_TOKEN_HERE" }')
        print("\n🔧 Export for local use:")
        print(f"export JWT_TOKEN=\"{token}\"")
        print("\n⚠️  SECURITY WARNING: Token displayed in plaintext!")
    else:
        # Show truncated token for security
        truncated = token[:20] + "..." + token[-10:] if len(token) > 30 else token
        print(f"\n🔑 Token (truncated): {truncated}")
        print("\n📋 Example usage in WebSocket messages:")
        print('{ "type": "auth", "token": "YOUR_TOKEN_HERE" }')
        print("\n🔧 Export for local use:")
        print("export JWT_TOKEN=\"<paste token here>\"")
        print("\n💡 Use --show-full-token to display the complete token (security risk)")

        # Save to secure location instead
        print(f"\n💾 Full token saved to: /tmp/matilda_token_{args.client_name.replace(' ', '_').lower()}.txt")
        try:
            import os

            token_file = f"/tmp/matilda_token_{args.client_name.replace(' ', '_').lower()}.txt"
            with open(token_file, "w") as f:
                f.write(token)
            os.chmod(token_file, 0o600)  # Only readable by owner
        except Exception:
            print("   (Failed to save file - token only in memory)")

    print(f"\n🌐 Connection URL: wss://{config.websocket_connect_host}:{config.websocket_port}")
    print("\n⚠️  Keep this token secure - anyone with it can access your transcription service!")


if __name__ == "__main__":
    main()
