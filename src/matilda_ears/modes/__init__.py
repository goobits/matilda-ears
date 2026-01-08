#!/usr/bin/env python3
"""GOOBITS STT Operation Modes

This module contains different operation modes for the STT engine:
- conversation: Continuous VAD-based listening
- tap_to_talk: Hotkey toggle recording
- hold_to_talk: Push-to-talk recording
"""

from typing import Optional, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from .conversation import ConversationMode as ConversationModeType
    from .tap_to_talk import TapToTalkMode as TapToTalkModeType
    from .hold_to_talk import HoldToTalkMode as HoldToTalkModeType

# Import modes conditionally to avoid dependency issues
ConversationMode: type | None = None
try:
    from .conversation import ConversationMode
except ImportError:
    pass

TapToTalkMode: type | None = None
try:
    from .tap_to_talk import TapToTalkMode
except ImportError:
    pass

HoldToTalkMode: type | None = None
try:
    from .hold_to_talk import HoldToTalkMode
except ImportError:
    pass

WakeWordMode: type | None = None
try:
    from ..wake_word.mode import WakeWordMode
except ImportError:
    pass

__all__ = ["ConversationMode", "HoldToTalkMode", "TapToTalkMode", "WakeWordMode"]
