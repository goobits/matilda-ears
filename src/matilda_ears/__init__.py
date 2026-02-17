"""GOOBITS STT - Pure speech-to-text engine with multiple operation modes."""

from importlib import metadata
from importlib import import_module
from pathlib import Path
import tomllib
from typing import TYPE_CHECKING


def _get_version() -> str:
    try:
        return metadata.version("goobits-matilda-ears")
    except Exception:
        pass

    try:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return str(data["project"]["version"])
    except Exception:
        return "unknown"


__version__ = _get_version()

if TYPE_CHECKING:
    from .core.config import ConfigLoader, get_config
    from .core.mode_config import (
        ConversationConfig,
        FileTranscribeConfig,
        ListenOnceConfig,
        ModeConfig,
    )
    from .core.vad_state import VADEvent, VADState, VADStateMachine
    from .modes import ConversationMode, WakeWordMode
    from .transcription.backends import (
        get_available_backends,
        get_backend_class,
        get_recommended_backend,
    )

_LAZY_EXPORTS = {
    "ConversationMode": (".modes", "ConversationMode"),
    "WakeWordMode": (".modes", "WakeWordMode"),
    "VADEvent": (".core.vad_state", "VADEvent"),
    "VADState": (".core.vad_state", "VADState"),
    "VADStateMachine": (".core.vad_state", "VADStateMachine"),
    "ConfigLoader": (".core.config", "ConfigLoader"),
    "get_config": (".core.config", "get_config"),
    "ModeConfig": (".core.mode_config", "ModeConfig"),
    "ConversationConfig": (".core.mode_config", "ConversationConfig"),
    "ListenOnceConfig": (".core.mode_config", "ListenOnceConfig"),
    "FileTranscribeConfig": (".core.mode_config", "FileTranscribeConfig"),
    "get_backend_class": (".transcription.backends", "get_backend_class"),
    "get_available_backends": (".transcription.backends", "get_available_backends"),
    "get_recommended_backend": (".transcription.backends", "get_recommended_backend"),
}


def __getattr__(name):
    if name in {"core", "modes", "transcription"}:
        module = import_module(f".{name}", __name__)
        globals()[name] = module
        return module

    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _LAZY_EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = [
    "ConversationMode",
    "WakeWordMode",
    "VADEvent",
    "VADState",
    "VADStateMachine",
    "ConfigLoader",
    "get_config",
    "ModeConfig",
    "ConversationConfig",
    "ListenOnceConfig",
    "FileTranscribeConfig",
    "get_backend_class",
    "get_available_backends",
    "get_recommended_backend",
]
