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
from src.core.config import get_config
from src.core.token_manager import TokenManager

# Module-level config instance (tests patch this)
config = get_config()

__all__ = [
    "MatildaWebSocketServer",
    "EnhancedWebSocketServer",
    "WebSocketTranscriptionServer",
    "main",
    "get_config",
    "TokenManager",
    "config",
    "sys",
]
