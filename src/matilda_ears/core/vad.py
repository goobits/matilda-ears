"""Voice Activity Detection (VAD) Processor.

Encapsulates the state machine for detecting speech start/end using Silero VAD.
"""

import logging
from enum import Enum

import numpy as np

try:
    from matilda_ears.audio.vad import SileroVAD
except ImportError:
    SileroVAD = None


class VADState(Enum):
    SILENCE = "silence"
    SPEECH = "speech"


class VADEvent(Enum):
    NONE = "none"
    START = "start"
    END = "end"


class VADProcessor:
    """State machine for processing audio chunks and detecting utterances."""

    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_speech_duration_s: float = 0.3,
        max_silence_duration_s: float = 0.8,
        chunks_per_second: int = 10,
    ):
        self.logger = logging.getLogger(__name__)
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_duration_s = min_speech_duration_s
        self.max_silence_duration_s = max_silence_duration_s
        self.chunks_per_second = chunks_per_second

        # State
        self.vad_model: SileroVAD | None = None
        self.state = VADState.SILENCE
        self.consecutive_speech = 0
        self.consecutive_silence = 0
        self.utterance_chunks: list[np.ndarray] = []
        self.speech_start_time = 0.0  # relative to stream start or chunk count

    def initialize(self) -> None:
        """Initialize the underlying VAD model."""
        if self.vad_model is not None:
            return

        try:
            self.logger.info("Initializing Silero VAD...")
            self.vad_model = SileroVAD(
                sample_rate=self.sample_rate,
                threshold=self.threshold,
                min_speech_duration=self.min_speech_duration_s,
                min_silence_duration=self.max_silence_duration_s,
                use_onnx=True,
            )
            self.logger.info("Silero VAD initialized successfully")
        except ImportError:
            self.logger.error("VAD dependencies missing")
            raise RuntimeError("Install dependencies: pip install torch torchaudio silero-vad")
        except Exception as e:
            self.logger.error(f"Failed to initialize VAD: {e}")
            raise

    def process(self, chunk: np.ndarray) -> tuple[VADEvent, float]:
        """Process a single audio chunk.

        Returns:
            Tuple of (VADEvent, speech_probability)

        """
        if self.vad_model is None:
            return VADEvent.NONE, 0.0

        speech_prob = self.vad_model.process_chunk(chunk)
        event = VADEvent.NONE

        if self.state == VADState.SILENCE:
            if speech_prob > self.threshold:
                self.consecutive_speech += 1
                if self.consecutive_speech >= 2:  # Require 2 chunks to confirm start
                    self.state = VADState.SPEECH
                    self.consecutive_silence = 0
                    self.utterance_chunks = []
                    # Backfill the trigger chunks
                    self.utterance_chunks.append(chunk)
                    event = VADEvent.START
            else:
                self.consecutive_speech = 0

        elif self.state == VADState.SPEECH:
            self.utterance_chunks.append(chunk)

            if speech_prob < (self.threshold - 0.15):  # Hysteresis
                self.consecutive_silence += 1
                self.consecutive_speech = 0
                
                # Check for end of utterance
                required_silence_chunks = int(self.max_silence_duration_s * self.chunks_per_second)
                
                if self.consecutive_silence >= required_silence_chunks:
                    # Validate duration
                    duration_s = len(self.utterance_chunks) / self.chunks_per_second
                    if duration_s >= self.min_speech_duration_s:
                        event = VADEvent.END
                        self.state = VADState.SILENCE
                        self.consecutive_silence = 0
                        self.consecutive_speech = 0
                    else:
                        # Too short, discard and reset
                        self.logger.debug(f"Utterance too short ({duration_s:.2f}s), discarding")
                        self.state = VADState.SILENCE
                        self.utterance_chunks = []
                        self.consecutive_silence = 0
                        self.consecutive_speech = 0
            else:
                self.consecutive_silence = 0
                self.consecutive_speech += 1

        return event, speech_prob

    def get_audio(self) -> np.ndarray:
        """Get the accumulated audio for the current/last utterance."""
        if not self.utterance_chunks:
            return np.array([], dtype=np.float32)
        return np.concatenate(self.utterance_chunks)

    def reset(self) -> None:
        """Reset state."""
        self.state = VADState.SILENCE
        self.consecutive_speech = 0
        self.consecutive_silence = 0
        self.utterance_chunks = []
        if self.vad_model:
            self.vad_model.reset()
