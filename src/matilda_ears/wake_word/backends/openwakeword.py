"""OpenWakeWord backend for wake word detection.

Uses the OpenWakeWord library for neural network-based wake word detection.
Supports custom ONNX models and pre-trained wake words.
"""

import logging
from pathlib import Path

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)

# Lazy import to avoid loading if not used
_openwakeword_model = None

# Pre-trained models available in OpenWakeWord (work immediately, no training needed)
PRETRAINED_MODELS = [
    "alexa",
    "hey_mycroft",
    "hey_jarvis",
    "hey_rhasspy",
]

# Default wake phrase uses a pre-trained model that works out of the box
DEFAULT_AGENT_ALIASES = {"Matilda": ["hey_jarvis"]}


def _get_openwakeword_model():
    """Lazy import OpenWakeWord Model class."""
    global _openwakeword_model
    if _openwakeword_model is None:
        try:
            from openwakeword.model import Model

            _openwakeword_model = Model
        except ImportError as e:
            raise ImportError(
                "OpenWakeWord is required for wake word detection. " "Install with: pip install openwakeword"
            ) from e
    return _openwakeword_model


class OpenWakeWordBackend:
    """OpenWakeWord-based wake word detection.

    Processes 80ms audio chunks (1280 samples @ 16kHz) for optimal performance.
    Supports multiple agents with multiple wake word aliases each.
    """

    # Audio requirements
    SAMPLE_RATE = 16000
    CHUNK_SAMPLES = 1280  # 80ms optimal for OpenWakeWord
    CHUNK_DURATION_MS = 80

    def __init__(
        self,
        agent_aliases: dict[str, list[str]] | None = None,
        threshold: float = 0.5,
        models_dir: Path | None = None,
        noise_suppression: bool = True,
    ):
        """Initialize OpenWakeWord backend.

        Args:
            agent_aliases: Mapping of agent names to wake word aliases.
                   Example: {"Matilda": ["hey_matilda", "computer", "hey_jarvis"]}
            threshold: Detection confidence threshold (0.0-1.0).
            models_dir: Custom models directory. Defaults to wake_word/internal/models/.
            noise_suppression: Enable Speex noise suppression (Linux only).

        """
        if not NUMPY_AVAILABLE:
            raise ImportError("NumPy is required for wake word detection.")

        Model = _get_openwakeword_model()

        self.threshold = threshold
        self._phrase_to_agent: dict[str, str] = {}  # Reverse mapping
        self._models_dir = models_dir or Path(__file__).parent.parent / "internal" / "models"

        # Use provided aliases or default
        self._agent_aliases = agent_aliases if agent_aliases else DEFAULT_AGENT_ALIASES.copy()

        # Collect all wake phrases and build reverse mapping
        all_phrases = []
        for agent, phrases in self._agent_aliases.items():
            for phrase in phrases:
                # Normalize phrase (replace spaces with underscores, lowercase)
                normalized = phrase.lower().replace(" ", "_").replace("-", "_")
                all_phrases.append(normalized)
                # Warn if phrase collision (two agents mapping to same phrase)
                if normalized in self._phrase_to_agent:
                    existing_agent = self._phrase_to_agent[normalized]
                    logger.warning(
                        f"Wake phrase '{normalized}' already mapped to '{existing_agent}', "
                        f"overwriting with '{agent}'"
                    )
                self._phrase_to_agent[normalized] = agent
                logger.debug(f"Registered wake phrase '{normalized}' -> agent '{agent}'")

        # Resolve phrases to model paths (custom .onnx or pre-trained)
        model_specs = []
        for phrase in all_phrases:
            custom_model = self._models_dir / f"{phrase}.onnx"
            if custom_model.exists():
                model_specs.append(str(custom_model))
                logger.info(f"Using custom model: {custom_model}")
            elif phrase in PRETRAINED_MODELS:
                model_specs.append(phrase)
                logger.info(f"Using pre-trained model: {phrase}")
            else:
                # Try anyway - OpenWakeWord may have it
                model_specs.append(phrase)
                logger.warning(f"Model '{phrase}' not found locally, trying OpenWakeWord...")

        if not model_specs:
            raise RuntimeError(f"No wake word models to load. Configured aliases: {self._agent_aliases}")

        self._ensure_pretrained_models(model_specs)

        # Load single model with ALL wake phrases for efficiency
        try:
            self.model = Model(
                wakeword_models=model_specs,
                enable_speex_noise_suppression=noise_suppression,
            )
            logger.info(
                f"OpenWakeWordBackend initialized with {len(model_specs)} phrases "
                f"for {len(self._agent_aliases)} agents"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load wake word models: {e}") from e

    def detect(self, audio: "np.ndarray") -> tuple[str, str, float] | None:
        """Detect wake word in audio chunk.

        Args:
            audio: Audio samples as numpy array.
                   Should be 16kHz 16-bit PCM (1280 samples = 80ms).

        Returns:
            Tuple of (agent_name, wake_phrase, confidence) if detected, None otherwise.
            Example: ("Matilda", "computer", 0.87)

        """
        predictions = self._predict(audio)
        best_phrase, best_confidence = self._best_prediction(predictions, self.threshold)

        if best_phrase and best_phrase in self._phrase_to_agent:
            agent = self._phrase_to_agent[best_phrase]
            logger.info(f"Detected: agent='{agent}', phrase='{best_phrase}', confidence={best_confidence:.2%}")
            return (agent, best_phrase, best_confidence)

        return None

    def reset(self) -> None:
        """Reset model states (call between utterances)."""
        if hasattr(self.model, "reset"):
            self.model.reset()

    @property
    def loaded_agents(self) -> list[str]:
        """List of agents with registered wake words."""
        return list(self._agent_aliases.keys())

    @property
    def agent_aliases(self) -> dict[str, list[str]]:
        """Get the agent to wake phrases mapping."""
        return self._agent_aliases.copy()

    def _ensure_pretrained_models(self, model_specs: list[str]) -> None:
        """Download pre-trained models if needed."""
        try:
            import openwakeword
            from openwakeword import utils as oww_utils
        except Exception as e:
            logger.debug(f"Skipping wake word model download: {e}")
            return

        missing = []
        for spec in model_specs:
            if spec in getattr(openwakeword, "MODELS", {}):
                model_path = Path(openwakeword.MODELS[spec]["model_path"])
                if not model_path.exists():
                    missing.append(spec)

        if missing:
            logger.info(f"Downloading wake word models: {', '.join(missing)}")
            oww_utils.download_models(missing)

    def _predict(self, audio: "np.ndarray") -> dict[str, float]:
        """Run prediction on audio chunk."""
        return self.model.predict(audio)

    def _best_prediction(self, predictions: dict[str, float], min_threshold: float) -> tuple[str | None, float]:
        """Get best prediction above threshold."""
        best_phrase = None
        best_confidence = min_threshold

        for phrase, confidence in predictions.items():
            if confidence > best_confidence:
                best_phrase = phrase
                best_confidence = confidence

        return (best_phrase, best_confidence)
