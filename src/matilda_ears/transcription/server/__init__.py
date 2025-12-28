"""WebSocket server package for Matilda STT.

This package provides a modular WebSocket server for speech-to-text transcription.

Public API:
    - MatildaWebSocketServer: Main WebSocket server class
    - EnhancedWebSocketServer: Enhanced server with dual-mode support
    - WebSocketTranscriptionServer: Alias for EnhancedWebSocketServer
    - main: Main entry point function
"""
import sys  # Re-exported for backward compatibility (tests patch sys.exit)

from .core import (
    EnhancedWebSocketServer,
    MatildaWebSocketServer,
    WebSocketTranscriptionServer,
)
from .main import main

# Re-export for backward compatibility (tests patch these at module level)
from matilda_ears.core.config import get_config
from matilda_ears.core.token_manager import TokenManager

# Module-level config instance (tests patch this)
config = get_config()

__all__ = [
    "EnhancedWebSocketServer",
    "MatildaWebSocketServer",
    "TokenManager",
    "WebSocketTranscriptionServer",
    "config",
    "get_config",
    "main",
    "sys",
]
