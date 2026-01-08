#!/usr/bin/env python3
"""VAD Processor - Unified Voice Activity Detection state machine.

This module provides a centralized VADProcessor class that handles:
- State machine transitions (waiting/silence → speech → trailing)
- Hysteresis to prevent chattering at threshold boundaries
- Debouncing with consecutive chunk counters
- Configurable timing parameters
- Unified behavior across all listening modes
"""

import time
from dataclasses import dataclass, field
from enum import Enum


class VADState(Enum):
    """VAD state machine states."""

    WAITING = "waiting"      # No speech detected yet
    SPEECH = "speech"        # Currently in speech
    TRAILING = "trailing"    # Brief silence during speech (hysteresis zone)


@dataclass
class VADConfig:
    """Configuration for VAD processing.

    Attributes:
        threshold: Speech probability threshold (0.0-1.0)
        hysteresis: Offset below threshold to end speech (prevents chattering)
        min_speech_chunks: Consecutive chunks required to start speech
        min_speech_duration: Minimum speech duration in seconds
        max_silence_duration: Maximum silence before ending speech (seconds)
        chunks_per_second: Audio chunks per second (for timing calculations)

    """

    threshold: float = 0.5
    hysteresis: float = 0.15
    min_speech_chunks: int = 2
    min_speech_duration: float = 0.3
    max_silence_duration: float = 0.8
    chunks_per_second: int = 10  # 100ms chunks


@dataclass
class VADResult:
    """Result from VAD processing.

    Attributes:
        state: Current VAD state
        is_speech: Whether speech is currently detected
        utterance_complete: True if a complete utterance was detected
        speech_duration: Duration of current speech segment (seconds)
        should_buffer: Whether to add current chunk to utterance buffer

    """

    state: VADState
    is_speech: bool
    utterance_complete: bool
    speech_duration: float
    should_buffer: bool


@dataclass
class VADProcessor:
    """Unified VAD state machine for speech detection.

    This class centralizes the VAD logic previously duplicated across
    ListenOnce and Conversation modes, ensuring consistent behavior.

    Example usage:
        >>> config = VADConfig(threshold=0.5, max_silence_duration=0.8)
        >>> processor = VADProcessor(config)
        >>>
        >>> for audio_chunk in audio_stream:
        ...     speech_prob = vad_model.process_chunk(audio_chunk)
        ...     result = processor.process(speech_prob)
        ...
        ...     if result.should_buffer:
        ...         utterance_chunks.append(audio_chunk)
        ...
        ...     if result.utterance_complete:
        ...         # Process complete utterance
        ...         process_utterance(utterance_chunks)
        ...         utterance_chunks = []
    """

    config: VADConfig = field(default_factory=VADConfig)

    # State tracking
    state: VADState = field(default=VADState.WAITING, init=False)
    consecutive_speech: int = field(default=0, init=False)
    consecutive_silence: int = field(default=0, init=False)
    speech_start_time: float | None = field(default=None, init=False)

    def reset(self) -> None:
        """Reset the processor to initial state."""
        self.state = VADState.WAITING
        self.consecutive_speech = 0
        self.consecutive_silence = 0
        self.speech_start_time = None

    def process(self, speech_prob: float) -> VADResult:
        """Process a single audio chunk and update state machine.

        Args:
            speech_prob: Speech probability from VAD model (0.0-1.0)

        Returns:
            VADResult with current state and action flags

        """
        utterance_complete = False
        should_buffer = False

        # Determine if this chunk is speech based on threshold
        is_above_threshold = speech_prob > self.config.threshold
        is_below_hysteresis = speech_prob < (self.config.threshold - self.config.hysteresis)

        if self.state == VADState.WAITING:
            result = self._process_waiting(is_above_threshold)

        elif self.state == VADState.SPEECH:
            result = self._process_speech(is_above_threshold, is_below_hysteresis)
            utterance_complete = result[0]
            should_buffer = result[1]

        else:  # TRAILING (hysteresis zone)
            result = self._process_trailing(is_above_threshold, is_below_hysteresis)
            utterance_complete = result[0]
            should_buffer = result[1]

        # Calculate current speech duration
        speech_duration = 0.0
        if self.speech_start_time is not None:
            speech_duration = time.time() - self.speech_start_time

        return VADResult(
            state=self.state,
            is_speech=self.state in (VADState.SPEECH, VADState.TRAILING),
            utterance_complete=utterance_complete,
            speech_duration=speech_duration,
            should_buffer=should_buffer
        )

    def _process_waiting(self, is_above_threshold: bool) -> None:
        """Process chunk while in WAITING state."""
        if is_above_threshold:
            self.consecutive_speech += 1
            if self.consecutive_speech >= self.config.min_speech_chunks:
                # Transition to SPEECH state
                self.state = VADState.SPEECH
                # Backdate start time to account for debouncing delay
                backdate = 0.1 * self.consecutive_speech
                self.speech_start_time = time.time() - backdate
        else:
            self.consecutive_speech = 0

    def _process_speech(
        self,
        is_above_threshold: bool,
        is_below_hysteresis: bool
    ) -> tuple[bool, bool]:
        """Process chunk while in SPEECH state.

        Returns:
            Tuple of (utterance_complete, should_buffer)

        """
        utterance_complete = False
        should_buffer = True  # Always buffer during speech

        if is_above_threshold:
            # Strong speech signal
            self.consecutive_speech += 1
            self.consecutive_silence = 0

        elif is_below_hysteresis:
            # Below hysteresis threshold - likely silence
            self.consecutive_silence += 1
            self.consecutive_speech = 0

            # Check if silence is long enough to end utterance
            required_silence = int(self.config.max_silence_duration * self.config.chunks_per_second)
            if self.consecutive_silence >= required_silence:
                utterance_complete = self._check_utterance_complete()

        else:
            # In hysteresis zone - maintain state, keep buffering
            # This prevents state flipping at exact threshold boundary
            pass

        return (utterance_complete, should_buffer)

    def _process_trailing(
        self,
        is_above_threshold: bool,
        is_below_hysteresis: bool
    ) -> tuple[bool, bool]:
        """Process chunk while in TRAILING state (brief silence during speech).

        Returns:
            Tuple of (utterance_complete, should_buffer)

        """
        # Same logic as SPEECH state for now
        # TRAILING is semantically the same but allows for future differentiation
        return self._process_speech(is_above_threshold, is_below_hysteresis)

    def _check_utterance_complete(self) -> bool:
        """Check if current utterance meets minimum duration requirement.

        Returns:
            True if utterance is complete and valid, False if too short

        """
        if self.speech_start_time is None:
            return False

        speech_duration = time.time() - self.speech_start_time

        if speech_duration >= self.config.min_speech_duration:
            # Valid utterance - reset state
            self.state = VADState.WAITING
            self.consecutive_speech = 0
            self.consecutive_silence = 0
            self.speech_start_time = None
            return True
        else:
            # Too short - reset without completing
            self.state = VADState.WAITING
            self.consecutive_speech = 0
            self.consecutive_silence = 0
            self.speech_start_time = None
            return False

    @property
    def is_active(self) -> bool:
        """Check if VAD is currently detecting speech."""
        return self.state in (VADState.SPEECH, VADState.TRAILING)

    @property
    def current_speech_duration(self) -> float:
        """Get duration of current speech segment in seconds."""
        if self.speech_start_time is None:
            return 0.0
        return time.time() - self.speech_start_time
