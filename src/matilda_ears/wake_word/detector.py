#!/usr/bin/env python3
"""OpenWakeWord integration for Matilda Ears.

Provides wake word detection using the OpenWakeWord library.
Supports custom models and pre-trained wake words.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)

# Lazy import to avoid loading if not used
_openwakeword_model = None


def _get_openwakeword_model():
    """Lazy import OpenWakeWord Model class."""
    global _openwakeword_model
    if _openwakeword_model is None:
        try:
            from openwakeword.model import Model
            _openwakeword_model = Model
        except ImportError as e:
            raise ImportError(
                "OpenWakeWord is required for wake word detection. "
                "Install with: pip install openwakeword"
            ) from e
    return _openwakeword_model


class WakeWordDetector:
    """Detects wake words in audio using OpenWakeWord.

    Processes 80ms audio chunks (1280 samples @ 16kHz) for optimal performance.
    Supports multiple agents with separate wake words (e.g., "Hey Matilda", "Hey Bob").
    """

    # Audio requirements
    SAMPLE_RATE = 16000
    CHUNK_SAMPLES = 1280  # 80ms optimal for OpenWakeWord
    CHUNK_DURATION_MS = 80

    def __init__(
        self,
        agents: Optional[List[str]] = None,
        threshold: float = 0.5,
        models_dir: Optional[Path] = None,
        noise_suppression: bool = True,
    ):
        """Initialize wake word detector.

        Args:
            agents: Agent names to detect (e.g., ["Matilda", "Bob"]).
                   Defaults to ["Matilda"].
            threshold: Detection confidence threshold (0.0-1.0).
            models_dir: Custom models directory. Defaults to wake_word/models/.
            noise_suppression: Enable Speex noise suppression (Linux only).
        """
        if not NUMPY_AVAILABLE:
            raise ImportError("NumPy is required for wake word detection.")

        Model = _get_openwakeword_model()

        self.agents = agents or ["Matilda"]
        self.threshold = threshold
        self.models: Dict[str, object] = {}
        self._wake_phrases: Dict[str, str] = {}

        # Determine models directory
        if models_dir is None:
            models_dir = Path(__file__).parent / "models"

        for agent in self.agents:
            wake_phrase = f"hey_{agent.lower()}"
            self._wake_phrases[agent] = wake_phrase
            custom_model = models_dir / f"{wake_phrase}.onnx"

            try:
                if custom_model.exists():
                    # Use custom trained model
                    self.models[agent] = Model(
                        wakeword_models=[str(custom_model)],
                        enable_speex_noise_suppression=noise_suppression,
                    )
                    logger.info(f"Loaded custom model: {custom_model}")
                else:
                    # Try pre-trained model (hey_jarvis, hey_mycroft, etc.)
                    self.models[agent] = Model(
                        wakeword_models=[wake_phrase],
                        enable_speex_noise_suppression=noise_suppression,
                    )
                    logger.info(f"Loaded pre-trained model: {wake_phrase}")
            except Exception as e:
                logger.warning(f"Model for '{agent}' not available: {e}")

        if not self.models:
            raise RuntimeError(
                f"No wake word models loaded. "
                f"Tried: {[f'hey_{a.lower()}' for a in self.agents]}"
            )

        logger.info(f"WakeWordDetector initialized with agents: {self.loaded_agents}")

    def detect(self, audio: "np.ndarray") -> Optional[str]:
        """Detect wake word in audio chunk.

        Args:
            audio: Audio samples as numpy array.
                   Should be 16kHz 16-bit PCM (1280 samples = 80ms).

        Returns:
            Agent name if wake word detected, None otherwise.
        """
        for agent, model in self.models.items():
            wake_phrase = self._wake_phrases[agent]
            predictions = model.predict(audio)

            confidence = predictions.get(wake_phrase, 0.0)
            if confidence > self.threshold:
                logger.info(f"Detected: {agent} (confidence: {confidence:.2%})")
                return agent

        return None

    def reset(self):
        """Reset model states (call between utterances)."""
        for model in self.models.values():
            if hasattr(model, "reset"):
                model.reset()

    @property
    def loaded_agents(self) -> List[str]:
        """List of agents with successfully loaded models."""
        return list(self.models.keys())
