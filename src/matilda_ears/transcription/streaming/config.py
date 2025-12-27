"""Streaming configuration from config.json.

Provides StreamingConfig with sensible defaults and stabilization presets.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional

from ...core.config import get_config

# Stabilization presets
STABILIZATION_PRESETS = {
    "low": {
        "local_agreement_n": 1,
        "transcribe_interval_seconds": 1.0,
        "prompt_suffix_chars": 120,
    },
    "medium": {
        "local_agreement_n": 2,
        "transcribe_interval_seconds": 2.0,
        "prompt_suffix_chars": 200,
    },
    "high": {
        "local_agreement_n": 3,
        "transcribe_interval_seconds": 3.0,
        "prompt_suffix_chars": 300,
    },
}


@dataclass
class StreamingConfig:
    """Configuration for streaming transcription sessions.

    Loaded from config.json["streaming"] with sensible defaults.
    """

    # Audio buffer settings
    max_buffer_seconds: float = 30.0
    sample_rate: int = 16000

    # Transcription timing
    transcribe_interval_seconds: float = 2.0
    session_timeout_seconds: float = 300.0

    # LocalAgreement settings
    local_agreement_n: int = 2
    prompt_suffix_chars: int = 200

    # Bounded history
    max_confirmed_words: int = 500

    # Stabilization preset (overrides individual settings if set)
    stabilization: Optional[Literal["low", "medium", "high"]] = None

    # Strategy selection
    strategy: Literal["local_agreement", "chunked", "native"] = "local_agreement"

    # Backend-specific
    enable_word_timestamps: bool = True

    @classmethod
    def from_config(cls) -> "StreamingConfig":
        """Load streaming config from config.json."""
        config = get_config()
        streaming_cfg = config.get("streaming", {})

        # Start with defaults
        instance = cls(
            max_buffer_seconds=streaming_cfg.get("max_buffer_seconds", 30.0),
            sample_rate=streaming_cfg.get("sample_rate", 16000),
            transcribe_interval_seconds=streaming_cfg.get("transcribe_interval_seconds", 2.0),
            session_timeout_seconds=streaming_cfg.get("session_timeout_seconds", 300.0),
            local_agreement_n=streaming_cfg.get("local_agreement_n", 2),
            prompt_suffix_chars=streaming_cfg.get("prompt_suffix_chars", 200),
            max_confirmed_words=streaming_cfg.get("max_confirmed_words", 500),
            stabilization=streaming_cfg.get("stabilization"),
            strategy=streaming_cfg.get("strategy", "local_agreement"),
            enable_word_timestamps=streaming_cfg.get("enable_word_timestamps", True),
        )

        # Apply stabilization preset if specified
        if instance.stabilization and instance.stabilization in STABILIZATION_PRESETS:
            preset = STABILIZATION_PRESETS[instance.stabilization]
            instance.local_agreement_n = preset["local_agreement_n"]
            instance.transcribe_interval_seconds = preset["transcribe_interval_seconds"]
            instance.prompt_suffix_chars = preset["prompt_suffix_chars"]

        return instance

    @property
    def max_buffer_samples(self) -> int:
        """Maximum buffer size in samples."""
        return int(self.max_buffer_seconds * self.sample_rate)

    @property
    def transcribe_interval_samples(self) -> int:
        """Transcription interval in samples."""
        return int(self.transcribe_interval_seconds * self.sample_rate)
