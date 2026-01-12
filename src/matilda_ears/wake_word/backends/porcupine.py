"""Porcupine backend for wake word detection.

Uses Picovoice Porcupine for low-latency, accurate wake word detection.
Requires an access key from Picovoice Console.
"""

import logging
import os
from pathlib import Path

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)

# Built-in Porcupine keywords (available without custom training)
BUILTIN_KEYWORDS = [
    "alexa",
    "americano",
    "blueberry",
    "bumblebee",
    "computer",
    "grapefruit",
    "grasshopper",
    "hey barista",
    "hey google",
    "hey siri",
    "jarvis",
    "ok google",
    "picovoice",
    "porcupine",
    "terminator",
]

DEFAULT_AGENT_ALIASES = {"Matilda": ["jarvis"]}


class PorcupineBackend:
    """Porcupine-based wake word detection.

    Uses Picovoice Porcupine for efficient, low-latency wake word detection.
    Processes 512 samples per frame at 16kHz (32ms).
    """

    SAMPLE_RATE = 16000
    CHUNK_SAMPLES = 512  # Porcupine frame size
    CHUNK_DURATION_MS = 32

    def __init__(
        self,
        agent_aliases: dict[str, list[str]] | None = None,
        threshold: float = 0.5,
        access_key: str | None = None,
        models_dir: Path | None = None,
        **kwargs,
    ):
        """Initialize Porcupine backend.

        Args:
            agent_aliases: Mapping of agent names to wake word aliases.
            threshold: Sensitivity (0.0-1.0). Higher = more sensitive.
            access_key: Picovoice access key. Falls back to PORCUPINE_ACCESS_KEY env var.
            models_dir: Directory for custom .ppn model files.

        """
        if not NUMPY_AVAILABLE:
            raise ImportError("NumPy is required for wake word detection.")

        try:
            import pvporcupine
        except ImportError as e:
            raise ImportError("Porcupine is required for this backend. " "Install with: pip install pvporcupine") from e

        # Get access key
        self._access_key = access_key or os.environ.get("PORCUPINE_ACCESS_KEY")
        if not self._access_key:
            raise ValueError(
                "Porcupine requires an access key. "
                "Set PORCUPINE_ACCESS_KEY env var or pass access_key parameter. "
                "Get a free key at: https://console.picovoice.ai/"
            )

        self.threshold = threshold
        self._phrase_to_agent: dict[str, str] = {}
        self._keyword_to_index: dict[str, int] = {}
        self._models_dir = models_dir or Path(__file__).parent.parent / "internal" / "models"

        # Use provided aliases or default
        self._agent_aliases = agent_aliases if agent_aliases else DEFAULT_AGENT_ALIASES.copy()

        # Collect keywords and build mappings
        keywords = []
        keyword_paths = []
        sensitivities = []

        for agent, phrases in self._agent_aliases.items():
            for phrase in phrases:
                normalized = phrase.lower().replace("_", " ").replace("-", " ")

                # Check for custom .ppn model
                custom_model = self._models_dir / f"{phrase.replace(' ', '_')}.ppn"
                if custom_model.exists():
                    keyword_paths.append(str(custom_model))
                    keywords.append(None)  # Custom path, no builtin keyword
                    logger.info(f"Using custom Porcupine model: {custom_model}")
                elif normalized in BUILTIN_KEYWORDS:
                    keywords.append(normalized)
                    keyword_paths.append(None)
                    logger.info(f"Using built-in Porcupine keyword: {normalized}")
                else:
                    logger.warning(
                        f"Keyword '{phrase}' not found. " f"Available built-in: {', '.join(BUILTIN_KEYWORDS[:5])}..."
                    )
                    continue

                self._phrase_to_agent[normalized] = agent
                self._keyword_to_index[normalized] = len(sensitivities)
                sensitivities.append(threshold)

        if not sensitivities:
            raise RuntimeError(
                f"No valid Porcupine keywords found. "
                f"Configured aliases: {self._agent_aliases}. "
                f"Built-in keywords: {BUILTIN_KEYWORDS}"
            )

        # Build keyword arguments
        porcupine_kwargs = {
            "access_key": self._access_key,
            "sensitivities": sensitivities,
        }

        # Add keywords or paths (not both)
        builtin = [k for k in keywords if k is not None]
        custom = [p for p in keyword_paths if p is not None]

        if builtin and not custom:
            porcupine_kwargs["keywords"] = builtin
        elif custom and not builtin:
            porcupine_kwargs["keyword_paths"] = custom
        elif builtin and custom:
            # Mix of builtin and custom - need to use paths for all
            # Convert builtin keywords to their default paths
            all_paths = []
            for kw, path in zip(keywords, keyword_paths, strict=True):
                if path:
                    all_paths.append(path)
                else:
                    # Use builtin keyword directly (Porcupine handles this)
                    all_paths.append(kw)
            porcupine_kwargs["keywords"] = [k for k in keywords if k]
            if custom:
                porcupine_kwargs["keyword_paths"] = custom

        try:
            self._porcupine = pvporcupine.create(**porcupine_kwargs)
            logger.info(
                f"PorcupineBackend initialized with {len(sensitivities)} keywords "
                f"for {len(self._agent_aliases)} agents"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Porcupine: {e}") from e

        # Store keyword list for index lookup
        self._keywords = builtin if builtin else [Path(p).stem for p in custom]

    def detect(self, audio: "np.ndarray") -> tuple[str, str, float] | None:
        """Detect wake word in audio chunk.

        Args:
            audio: Audio samples as numpy array (512 samples @ 16kHz, int16).

        Returns:
            Tuple of (agent_name, wake_phrase, confidence) if detected, None otherwise.
            Note: Porcupine doesn't provide confidence scores, returns 1.0 on detection.

        """
        if audio.size < self.CHUNK_SAMPLES:
            return None

        # Porcupine expects int16
        if audio.dtype != np.int16:
            if audio.dtype == np.float32 or audio.dtype == np.float64:
                audio = (audio * 32767).astype(np.int16)
            else:
                audio = audio.astype(np.int16)

        # Process frame
        keyword_index = self._porcupine.process(audio[: self.CHUNK_SAMPLES])

        if keyword_index >= 0:
            keyword = self._keywords[keyword_index]
            normalized = keyword.lower().replace("_", " ").replace("-", " ")
            agent = self._phrase_to_agent.get(normalized, "Unknown")
            logger.info(f"Detected: agent='{agent}', phrase='{keyword}', confidence=100%")
            return (agent, keyword, 1.0)

        return None

    def reset(self) -> None:
        """Reset state between utterances.

        Porcupine is stateless per-frame, no reset needed.
        """

    @property
    def loaded_agents(self) -> list[str]:
        """List of agents with registered wake words."""
        return list(self._agent_aliases.keys())

    @property
    def agent_aliases(self) -> dict[str, list[str]]:
        """Get the agent to wake phrases mapping."""
        return self._agent_aliases.copy()

    def __del__(self):
        """Clean up Porcupine resources."""
        if hasattr(self, "_porcupine") and self._porcupine:
            self._porcupine.delete()
