#!/usr/bin/env python3
"""OpenWakeWord integration for Matilda Ears.

Provides wake word detection using the OpenWakeWord library.
Supports custom models, pre-trained wake words, and multiple aliases per agent.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)

# Lazy import to avoid loading if not used
_openwakeword_model = None

# Pre-trained models available in OpenWakeWord
PRETRAINED_MODELS = [
    "alexa",
    "hey_mycroft",
    "hey_jarvis",
    "hey_rhasspy",
]


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
    Supports multiple agents with multiple wake word aliases each.

    Examples:
        # Simple: one agent, one wake word
        detector = WakeWordDetector(agents=["Matilda"])

        # Advanced: one agent with multiple aliases
        detector = WakeWordDetector(
            agent_aliases={"Matilda": ["hey_matilda", "computer", "hey_jarvis"]}
        )

        # Multi-agent with aliases
        detector = WakeWordDetector(
            agent_aliases={
                "Matilda": ["hey_matilda", "computer", "assistant"],
                "Bob": ["hey_bob", "hey_mycroft"],
            }
        )
    """

    # Audio requirements
    SAMPLE_RATE = 16000
    CHUNK_SAMPLES = 1280  # 80ms optimal for OpenWakeWord
    CHUNK_DURATION_MS = 80

    def __init__(
        self,
        agents: Optional[List[str]] = None,
        agent_aliases: Optional[Dict[str, List[str]]] = None,
        threshold: float = 0.5,
        models_dir: Optional[Path] = None,
        noise_suppression: bool = True,
    ):
        """Initialize wake word detector.

        Args:
            agents: Simple agent names to detect (e.g., ["Matilda", "Bob"]).
                   Each agent responds to "hey_{name}". Defaults to ["Matilda"].
            agent_aliases: Advanced mapping of agent names to wake word aliases.
                   Example: {"Matilda": ["hey_matilda", "computer", "hey_jarvis"]}
                   Takes precedence over `agents` if both provided.
            threshold: Detection confidence threshold (0.0-1.0).
            models_dir: Custom models directory. Defaults to wake_word/models/.
            noise_suppression: Enable Speex noise suppression (Linux only).
        """
        if not NUMPY_AVAILABLE:
            raise ImportError("NumPy is required for wake word detection.")

        Model = _get_openwakeword_model()

        self.threshold = threshold
        self._phrase_to_agent: Dict[str, str] = {}  # Reverse mapping
        self._models_dir = models_dir or Path(__file__).parent / "models"

        # Build agent aliases mapping
        if agent_aliases:
            self._agent_aliases = agent_aliases
        elif agents:
            # Legacy format: simple agent list
            self._agent_aliases = {agent: [f"hey_{agent.lower()}"] for agent in agents}
        else:
            # Default
            self._agent_aliases = {"Matilda": ["hey_matilda"]}

        # Collect all wake phrases and build reverse mapping
        all_phrases = []
        for agent, phrases in self._agent_aliases.items():
            for phrase in phrases:
                # Normalize phrase (replace spaces with underscores, lowercase)
                normalized = phrase.lower().replace(" ", "_").replace("-", "_")
                all_phrases.append(normalized)
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
            raise RuntimeError(
                f"No wake word models to load. "
                f"Configured aliases: {self._agent_aliases}"
            )

        # Load single model with ALL wake phrases for efficiency
        try:
            self.model = Model(
                wakeword_models=model_specs,
                enable_speex_noise_suppression=noise_suppression,
            )
            logger.info(
                f"WakeWordDetector initialized with {len(model_specs)} phrases "
                f"for {len(self._agent_aliases)} agents"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load wake word models: {e}") from e

    def detect(self, audio: "np.ndarray") -> Optional[Tuple[str, str, float]]:
        """Detect wake word in audio chunk.

        Args:
            audio: Audio samples as numpy array.
                   Should be 16kHz 16-bit PCM (1280 samples = 80ms).

        Returns:
            Tuple of (agent_name, wake_phrase, confidence) if detected, None otherwise.
            Example: ("Matilda", "computer", 0.87)
        """
        predictions = self.model.predict(audio)

        # Find highest confidence above threshold
        best_phrase = None
        best_confidence = self.threshold

        for phrase, confidence in predictions.items():
            if confidence > best_confidence:
                best_phrase = phrase
                best_confidence = confidence

        if best_phrase and best_phrase in self._phrase_to_agent:
            agent = self._phrase_to_agent[best_phrase]
            logger.info(
                f"Detected: agent='{agent}', phrase='{best_phrase}', "
                f"confidence={best_confidence:.2%}"
            )
            return (agent, best_phrase, best_confidence)

        return None

    def detect_agent(self, audio: "np.ndarray") -> Optional[str]:
        """Detect wake word and return just the agent name.

        Convenience method for backward compatibility.

        Args:
            audio: Audio samples as numpy array.

        Returns:
            Agent name if wake word detected, None otherwise.
        """
        result = self.detect(audio)
        return result[0] if result else None

    def reset(self):
        """Reset model states (call between utterances)."""
        if hasattr(self.model, "reset"):
            self.model.reset()

    @property
    def loaded_agents(self) -> List[str]:
        """List of agents with registered wake words."""
        return list(self._agent_aliases.keys())

    @property
    def agent_aliases(self) -> Dict[str, List[str]]:
        """Get the agent to wake phrases mapping."""
        return self._agent_aliases.copy()

    @classmethod
    def from_config(
        cls,
        config: Dict,
        models_dir: Optional[Path] = None,
    ) -> "WakeWordDetector":
        """Create detector from configuration dict.

        Args:
            config: Configuration dict with wake_word settings.
                   Supports both legacy 'agents' list and new 'agent_aliases' format.
            models_dir: Optional custom models directory.

        Returns:
            Configured WakeWordDetector instance.

        Example config (new format):
            {
                "agent_aliases": [
                    {"agent": "Matilda", "aliases": ["hey_matilda", "computer"]},
                    {"agent": "Bob", "aliases": ["hey_bob"]}
                ],
                "threshold": 0.5,
                "noise_suppression": true
            }

        Example config (legacy format):
            {
                "agents": ["Matilda", "Bob"],
                "threshold": 0.5
            }
        """
        # Parse agent aliases
        agent_aliases = None
        agents = None

        if "agent_aliases" in config:
            # New format: list of {agent, aliases} dicts
            agent_aliases = {}
            for item in config["agent_aliases"]:
                agent_aliases[item["agent"]] = item["aliases"]
        elif "agents" in config:
            # Legacy format: simple list
            agents = config["agents"]

        return cls(
            agents=agents,
            agent_aliases=agent_aliases,
            threshold=config.get("threshold", 0.5),
            models_dir=models_dir,
            noise_suppression=config.get("noise_suppression", True),
        )

    @classmethod
    def parse_cli_aliases(cls, aliases_str: str) -> Dict[str, List[str]]:
        """Parse agent aliases from CLI string format.

        Args:
            aliases_str: CLI format string.
                        Format: "Agent1:phrase1,phrase2;Agent2:phrase3,phrase4"
                        Example: "Matilda:hey_matilda,computer;Bob:hey_bob"

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
