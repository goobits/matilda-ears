"""Wake word detection module for Matilda Ears.

All wake word functionality is contained in this module.
Provides hands-free "Hey Matilda" activation using OpenWakeWord.
"""

__all__ = ["WakeWordDetector", "WakeWordMode", "get_detector", "get_mode"]


def get_detector():
    """Get WakeWordDetector class (lazy import)."""
    from .detector import WakeWordDetector

    return WakeWordDetector


def get_mode():
    """Get WakeWordMode class (lazy import)."""
    from .mode import WakeWordMode

    return WakeWordMode


# Lazy module-level imports for convenience
def __getattr__(name: str):
    """Lazy import for module-level access."""
    if name == "WakeWordDetector":
        from .detector import WakeWordDetector

        return WakeWordDetector
    if name == "WakeWordMode":
        from .mode import WakeWordMode

        return WakeWordMode
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
