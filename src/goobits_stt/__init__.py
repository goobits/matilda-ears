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

# Import key classes for easy access
from .modes.listen_once import ListenOnceMode
from .modes.conversation import ConversationMode
from .modes.tap_to_talk import TapToTalkMode
from .modes.hold_to_talk import HoldToTalkMode

__all__ = [
    "ListenOnceMode",
    "ConversationMode", 
    "TapToTalkMode",
    "HoldToTalkMode",
]