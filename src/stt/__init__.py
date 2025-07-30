"""
GOOBITS STT - Pure speech-to-text engine with multiple operation modes.

This package provides:
- Listen-once mode: Single utterance capture with VAD
- Conversation mode: Always listening with interruption support
- Tap-to-talk mode: Press key to start/stop recording
- Hold-to-talk mode: Hold key to record, release to stop
- WebSocket server mode: Remote client connections
"""

__version__ = "1.0.0"
__author__ = "GOOBITS Team"

# Classes are imported on-demand to avoid loading heavy dependencies at startup
# Import them with: from stt.modes.conversation import ConversationMode

__all__ = [
    "ConversationMode",
    "HoldToTalkMode", 
    "ListenOnceMode",
    "TapToTalkMode",
]
