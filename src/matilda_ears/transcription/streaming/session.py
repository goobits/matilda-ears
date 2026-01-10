"""Streaming session orchestrator.

StreamingSession coordinates the streaming pipeline:
- Receives audio chunks
- Delegates to strategy for processing
- Manages session lifecycle and timeout
- Returns StreamingResult to caller
"""

import time
import logging
from typing import TYPE_CHECKING

import numpy as np

from .config import StreamingConfig
from .types import (
    StreamingResult,
    StreamingMetrics,
    StreamingState,
    StreamingError,
    SessionTimeoutError,
)

if TYPE_CHECKING:
    from .strategies.protocol import StreamingStrategy

logger = logging.getLogger(__name__)


class StreamingSession:
    """Orchestrates a streaming transcription session.

    Manages the lifecycle of a single streaming session:
    1. Receives audio chunks from server handler
    2. Delegates to strategy for processing
    3. Tracks metrics and handles timeout
    4. Returns results for sending to client

    Example:
        session = StreamingSession(
            session_id="abc123",
            strategy=LocalAgreementStrategy(...),
            config=StreamingConfig.from_config()
        )

        # Process audio chunks
        result = await session.process_chunk(audio_data)

        # Finalize session
        final_result = await session.finalize()

    """

    def __init__(
        self,
        session_id: str,
        strategy: "StreamingStrategy",
        config: StreamingConfig,
    ):
        """Initialize streaming session.

        Args:
            session_id: Unique session identifier
            strategy: Streaming strategy to use
            config: Streaming configuration

        """
        self.session_id = session_id
        self.strategy = strategy
        self.config = config

        # State tracking
        self._state = StreamingState.IDLE
        self._start_time: float | None = None
        self._last_activity: float | None = None

        # Metrics
        self._metrics = StreamingMetrics(session_id=session_id)

        logger.info(f"StreamingSession created: {session_id}")

    @property
    def state(self) -> StreamingState:
        """Current session state."""
        return self._state

    @property
    def metrics(self) -> StreamingMetrics:
        """Current session metrics."""
        return self._metrics

    @property
    def is_active(self) -> bool:
        """Whether session is currently active."""
        return self._state == StreamingState.ACTIVE

    def _update_state(self, new_state: StreamingState) -> None:
        """Update session state and sync with metrics."""
        self._state = new_state
        self._metrics.state = new_state

    async def start(self) -> None:
        """Start the streaming session.

        Called when client sends start_stream message.
        """
        if self._state != StreamingState.IDLE:
            raise StreamingError(f"Session {self.session_id} already started")

        self._update_state(StreamingState.ACTIVE)
        self._start_time = time.time()
        self._last_activity = self._start_time
        self._metrics.session_start_time = self._start_time

        logger.info(f"StreamingSession started: {self.session_id}")

    async def process_chunk(self, audio_chunk: np.ndarray) -> StreamingResult:
        """Process an audio chunk and return partial result.

        Args:
            audio_chunk: Audio samples (float32 or int16)

        Returns:
            StreamingResult with confirmed/tentative text

        Raises:
            StreamingError: If session not active
            SessionTimeoutError: If session has timed out

        """
        # Check state
        if self._state == StreamingState.IDLE:
            # Auto-start on first chunk
            await self.start()
        elif self._state != StreamingState.ACTIVE:
            raise StreamingError(f"Session {self.session_id} not active (state={self._state.value})")

        # Check timeout
        now = time.time()
        if self._last_activity:
            idle_time = now - self._last_activity
            if idle_time > self.config.session_timeout_seconds:
                self._update_state(StreamingState.ERROR)
                raise SessionTimeoutError(self.session_id, self.config.session_timeout_seconds)

        self._last_activity = now

        # Update metrics
        self._metrics.chunks_received += 1
        chunk_duration = len(audio_chunk) / self.config.sample_rate
        self._metrics.total_audio_seconds += chunk_duration

        # Delegate to strategy
        start_time = time.time()
        try:
            result = await self.strategy.process_audio(audio_chunk)
        except Exception as e:
            logger.exception(f"Strategy error in session {self.session_id}: {e}")
            raise StreamingError(f"Processing failed: {e}") from e

        # Update metrics
        processing_time = (time.time() - start_time) * 1000
        result.processing_time_ms = processing_time
        result.audio_duration_seconds = self._metrics.total_audio_seconds

        self._metrics.last_activity_time = now
        self._metrics.confirmed_words = result.confirmed_word_count
        self._metrics.buffer_audio_seconds = chunk_duration  # Updated by strategy

        return result

    async def finalize(self) -> StreamingResult:
        """Finalize session and return final result.

        Flushes any remaining hypothesis and returns the complete transcription.

        Returns:
            Final StreamingResult with is_final=True

        """
        if self._state == StreamingState.COMPLETED:
            raise StreamingError(f"Session {self.session_id} already finalized")

        self._update_state(StreamingState.FINALIZING)

        logger.info(f"Finalizing session {self.session_id}")

        try:
            # Get final result from strategy
            result = await self.strategy.finalize()
            result.is_final = True
            result.audio_duration_seconds = self._metrics.total_audio_seconds

            self._update_state(StreamingState.COMPLETED)

            logger.info(
                f"Session {self.session_id} finalized: "
                f"{result.confirmed_word_count} words, "
                f"{self._metrics.total_audio_seconds:.2f}s audio"
            )

            return result

        except Exception as e:
            self._update_state(StreamingState.ERROR)
            logger.exception(f"Error finalizing session {self.session_id}: {e}")
            raise StreamingError(f"Finalization failed: {e}") from e

    async def abort(self) -> None:
        """Abort the session without finalizing.

        Used for cleanup when client disconnects unexpectedly.
        """
        if self._state in (StreamingState.COMPLETED, StreamingState.ERROR):
            return

        logger.warning(f"Aborting session {self.session_id}")
        self._update_state(StreamingState.ERROR)

        # Clean up strategy resources
        try:
            await self.strategy.cleanup()
        except Exception as e:
            logger.warning(f"Error during abort cleanup: {e}")

    def check_timeout(self) -> bool:
        """Check if session has timed out.

        Returns:
            True if session should be timed out

        """
        if not self._last_activity:
            return False

        idle_time = time.time() - self._last_activity
        return idle_time > self.config.session_timeout_seconds
