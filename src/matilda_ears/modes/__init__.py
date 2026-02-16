#!/usr/bin/env python3
"""GOOBITS STT Operation Modes

This module contains different operation modes for the STT engine:
- conversation: Continuous VAD-based listening
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .conversation import ConversationMode as ConversationModeType

# Import modes conditionally to avoid dependency issues
ConversationMode: type | None = None
try:
    from .conversation import ConversationMode
except ImportError:
    pass

WakeWordMode: type | None = None
try:
    from ..wake_word.mode import WakeWordMode
except ImportError:
    pass

__all__ = ["ConversationMode", "WakeWordMode"]
