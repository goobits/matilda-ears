"""Core package exports."""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .vad_state import VADEvent, VADState, VADStateMachine

__all__ = ["VADEvent", "VADState", "VADStateMachine"]

_LAZY_EXPORTS = {
    "VADEvent": (".vad_state", "VADEvent"),
    "VADState": (".vad_state", "VADState"),
    "VADStateMachine": (".vad_state", "VADStateMachine"),
}


def __getattr__(name):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _LAZY_EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
