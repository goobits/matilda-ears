"""Pluggable wake word detection backends.

Supports multiple wake word engines via a common interface.
"""

from pathlib import Path
from typing import Protocol

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class WakeWordBackend(Protocol):
    """Interface for wake word detection backends."""

    SAMPLE_RATE: int
    CHUNK_SAMPLES: int
    CHUNK_DURATION_MS: int

    def detect(self, audio: "np.ndarray") -> tuple[str, str, float] | None:
        """Detect wake word in audio chunk.

        Args:
            audio: Audio samples as numpy array (16kHz PCM).

        Returns:
            Tuple of (agent_name, wake_phrase, confidence) if detected, None otherwise.

        """
        ...

    def reset(self) -> None:
        """Reset internal state between utterances."""
        ...

    @property
    def loaded_agents(self) -> list[str]:
        """List of agents with registered wake words."""
        ...

    @property
    def agent_aliases(self) -> dict[str, list[str]]:
        """Get the agent to wake phrases mapping."""
        ...


def get_backend(
    name: str = "openwakeword",
    agent_aliases: dict[str, list[str]] | None = None,
    threshold: float = 0.5,
    models_dir: Path | None = None,
    noise_suppression: bool = True,
    access_key: str | None = None,
    **kwargs,
) -> WakeWordBackend:
    """Factory for wake word backends.

    Args:
        name: Backend name ("openwakeword" or "porcupine").
        agent_aliases: Mapping of agent names to wake word aliases.
        threshold: Detection confidence threshold (0.0-1.0).
        models_dir: Custom models directory.
        noise_suppression: Enable noise suppression (backend-specific).
        access_key: API key for backends that require it (e.g., Porcupine).

    Returns:
        Configured wake word backend instance.

    Raises:
        ValueError: If backend name is unknown.
        ImportError: If backend dependencies are not installed.

    """
    if name == "openwakeword":
        from .openwakeword import OpenWakeWordBackend

        return OpenWakeWordBackend(
            agent_aliases=agent_aliases,
            threshold=threshold,
            models_dir=models_dir,
            noise_suppression=noise_suppression,
        )
    elif name == "porcupine":
        from .porcupine import PorcupineBackend

        return PorcupineBackend(
            agent_aliases=agent_aliases,
            threshold=threshold,
            access_key=access_key,
        )
    else:
        raise ValueError(f"Unknown wake word backend: {name}. Available: openwakeword, porcupine")


__all__ = ["WakeWordBackend", "get_backend"]
