#!/usr/bin/env python3
"""Wake word detection with pluggable backends.

Provides a unified interface for wake word detection supporting multiple backends
(OpenWakeWord, Porcupine).
"""

import logging
from pathlib import Path

from .backends import WakeWordBackend, get_backend
from .backends.openwakeword import DEFAULT_AGENT_ALIASES, PRETRAINED_MODELS

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)

__all__ = [
    "WakeWordDetector",
    "WakeWordBackend",
    "get_backend",
    "DEFAULT_AGENT_ALIASES",
    "PRETRAINED_MODELS",
]

# Audio constants (OpenWakeWord defaults, may vary by backend)
SAMPLE_RATE = 16000
CHUNK_SAMPLES = 1280
CHUNK_DURATION_MS = 80


class WakeWordDetector:
    """Wake word detector with pluggable backend support.

    Delegates to configured backend (OpenWakeWord or Porcupine).

    Examples:
        # Default (OpenWakeWord)
        detector = WakeWordDetector()

        # Explicit backend selection
        detector = WakeWordDetector(backend="porcupine", access_key="...")

        # With agent aliases
        detector = WakeWordDetector(
            agent_aliases={"Matilda": ["hey_matilda", "computer"]}
        )

    """

    # Expose backend's audio requirements
    SAMPLE_RATE = SAMPLE_RATE
    CHUNK_SAMPLES = CHUNK_SAMPLES
    CHUNK_DURATION_MS = CHUNK_DURATION_MS

    def __init__(
        self,
        agent_aliases: dict[str, list[str]] | None = None,
        threshold: float = 0.5,
        models_dir: Path | None = None,
        noise_suppression: bool = True,
        backend: str = "openwakeword",
        access_key: str | None = None,
    ):
        """Initialize wake word detector.

        Args:
            agent_aliases: Mapping of agent names to wake word aliases.
            threshold: Detection confidence threshold (0.0-1.0).
            models_dir: Custom models directory.
            noise_suppression: Enable noise suppression (backend-specific).
            backend: Backend to use ("openwakeword" or "porcupine").
            access_key: API key for backends that require it (e.g., Porcupine).

        """
        if not NUMPY_AVAILABLE:
            raise ImportError("NumPy is required for wake word detection.")

        self._backend_name = backend
        self._backend: WakeWordBackend = get_backend(
            name=backend,
            agent_aliases=agent_aliases,
            threshold=threshold,
            models_dir=models_dir,
            noise_suppression=noise_suppression,
            access_key=access_key,
        )

        # Update class constants to match backend
        self.SAMPLE_RATE = self._backend.SAMPLE_RATE
        self.CHUNK_SAMPLES = self._backend.CHUNK_SAMPLES
        self.CHUNK_DURATION_MS = self._backend.CHUNK_DURATION_MS

        logger.info(f"WakeWordDetector using backend: {backend}")

    def detect(self, audio: "np.ndarray") -> tuple[str, str, float] | None:
        """Detect wake word in audio chunk.

        Args:
            audio: Audio samples as numpy array.

        Returns:
            Tuple of (agent_name, wake_phrase, confidence) if detected, None otherwise.

        """
        return self._backend.detect(audio)

    def detect_chunk(self, audio: "np.ndarray") -> tuple[str, str, float] | None:
        """Detect wake word in audio chunk (convenience wrapper)."""
        if audio.size == 0:
            return None
        return self.detect(audio)

    def best_score(self, audio: "np.ndarray") -> tuple[str | None, float]:
        """Get best prediction score without threshold filtering.

        Note: Only supported by OpenWakeWord backend.
        """
        if hasattr(self._backend, "best_score"):
            return self._backend.best_score(audio)
        # Fallback: just run detection
        result = self.detect(audio)
        if result:
            return (result[1], result[2])
        return (None, 0.0)

    def detect_agent(self, audio: "np.ndarray") -> str | None:
        """Detect wake word and return just the agent name."""
        result = self.detect(audio)
        return result[0] if result else None

    def reset(self) -> None:
        """Reset model states (call between utterances)."""
        self._backend.reset()

    @property
    def loaded_agents(self) -> list[str]:
        """List of agents with registered wake words."""
        return self._backend.loaded_agents

    @property
    def agent_aliases(self) -> dict[str, list[str]]:
        """Get the agent to wake phrases mapping."""
        return self._backend.agent_aliases

    @property
    def backend_name(self) -> str:
        """Get the name of the active backend."""
        return self._backend_name

    @classmethod
    def from_config(
        cls,
        config: dict,
        models_dir: Path | None = None,
    ) -> "WakeWordDetector":
        """Create detector from configuration dict.

        Args:
            config: Configuration dict with wake_word settings.
            models_dir: Optional custom models directory.

        Returns:
            Configured WakeWordDetector instance.

        Example config:
            {
                "backend": "openwakeword",
                "agent_aliases": [
                    {"agent": "Matilda", "aliases": ["hey_matilda", "computer"]},
                ],
                "threshold": 0.5,
                "noise_suppression": true
            }

        """
        agent_aliases = None
        if "agent_aliases" in config:
            if isinstance(config["agent_aliases"], list):
                # List of {agent, aliases} dicts
                agent_aliases = {}
                for item in config["agent_aliases"]:
                    agent_aliases[item["agent"]] = item["aliases"]
            else:
                # Direct dict format
                agent_aliases = config["agent_aliases"]

        return cls(
            agent_aliases=agent_aliases,
            threshold=config.get("threshold", 0.5),
            models_dir=models_dir,
            noise_suppression=config.get("noise_suppression", True),
            backend=config.get("backend", "openwakeword"),
            access_key=config.get("access_key"),
        )

    @classmethod
    def parse_cli_aliases(cls, aliases_str: str) -> dict[str, list[str]]:
        """Parse agent aliases from CLI string format.

        Args:
            aliases_str: CLI format string.
                        Format: "Agent1:phrase1,phrase2;Agent2:phrase3,phrase4"

        Returns:
            Dict mapping agent names to list of wake phrases.

        """
        result = {}
        for part in aliases_str.split(";"):
            part = part.strip()
            if not part or ":" not in part:
                continue
            agent, phrases_str = part.split(":", 1)
            phrases = [p.strip() for p in phrases_str.split(",") if p.strip()]
            if agent.strip() and phrases:
                result[agent.strip()] = phrases
        return result
