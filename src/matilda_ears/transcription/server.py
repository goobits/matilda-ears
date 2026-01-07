#!/usr/bin/env python3
"""WebSocket Matilda Server - Enables Mac clients to connect via WebSocket for speech-to-text.

Runs alongside the existing TCP server for local Ubuntu clients.

This module is a thin re-export facade. The actual implementation is in the server/ package.
"""
import os
import sys

# Check for management token
if os.environ.get("MATILDA_MANAGEMENT_TOKEN") != "managed-by-matilda-system":
    raise RuntimeError("This server must be started via ./server.py (Use: ./server.py start-ws)")


# Add project root to path for imports - cross-platform compatible
def ensure_project_root_in_path():
    """Ensure the project root is in sys.path for imports to work."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    while current_dir != os.path.dirname(current_dir):  # Stop at filesystem root
        if os.path.exists(os.path.join(current_dir, "pyproject.toml")) or os.path.exists(
            os.path.join(current_dir, "config.jsonc")
        ):
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            return current_dir
        current_dir = os.path.dirname(current_dir)

    # Fallback: assume we're in src/transcription/ and go up two levels
    fallback_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if fallback_root not in sys.path:
        sys.path.insert(0, fallback_root)
    return fallback_root


ensure_project_root_in_path()

# Environment setup for server
if os.environ.get("WEBSOCKET_SERVER_IP"):
    os.environ["WEBSOCKET_SERVER_HOST"] = os.environ["WEBSOCKET_SERVER_IP"]

# Re-export public API from server package
from .server import (  # noqa: E402
    EnhancedWebSocketServer,
    MatildaWebSocketServer,
    WebSocketTranscriptionServer,
    main,
)

# Re-export get_config for backward compatibility (tests patch this)
from matilda_ears.core.config import get_config  # noqa: E402

__all__ = [
    "EnhancedWebSocketServer",
    "MatildaWebSocketServer",
    "WebSocketTranscriptionServer",
    "get_config",
    "main",
]

if __name__ == "__main__":
    main()
