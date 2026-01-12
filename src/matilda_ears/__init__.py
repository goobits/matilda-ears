"""GOOBITS STT - Pure speech-to-text engine with multiple operation modes."""

__version__ = "1.0.0"

from .modes import (
    ConversationMode,
    HoldToTalkMode,
    TapToTalkMode,
    WakeWordMode,
)
from .core.vad_state import VADEvent, VADState, VADStateMachine
from .core.config import ConfigLoader, get_config
from .core.mode_config import (
    ConversationConfig,
    FileTranscribeConfig,
    HoldToTalkConfig,
    ListenOnceConfig,
    ModeConfig,
    TapToTalkConfig,
)
from .transcription.backends import (
    get_backend_class,
    get_available_backends,
    get_recommended_backend,
)

__all__ = [
    "ConversationMode",
    "HoldToTalkMode",
    "TapToTalkMode",
    "WakeWordMode",
    "VADEvent",
    "VADState",
    "VADStateMachine",
    "ConfigLoader",
    "get_config",
    "ModeConfig",
    "ConversationConfig",
    "ListenOnceConfig",
    "TapToTalkConfig",
    "HoldToTalkConfig",
    "FileTranscribeConfig",
    "get_backend_class",
    "get_available_backends",
    "get_recommended_backend",
]
