"""Factory for creating streaming sessions.

Provides create_streaming_session() that:
- Selects appropriate strategy based on backend and config
- Creates configured strategy and session
- Returns ready-to-use StreamingSession
"""

import asyncio
import logging
from typing import Callable, Awaitable, Optional, TYPE_CHECKING


from .config import StreamingConfig
from .session import StreamingSession
from .types import StreamingError

if TYPE_CHECKING:
    from ..backends.base import TranscriptionBackend

logger = logging.getLogger(__name__)

# Type alias for batch transcribe function
BatchTranscribeFn = Callable[[bytes, str], Awaitable[tuple]]


def create_streaming_session(
    session_id: str,
    backend: "TranscriptionBackend",
    config: Optional[StreamingConfig] = None,
    transcription_semaphore: Optional["asyncio.Semaphore"] = None,
) -> StreamingSession:
    """Create a streaming session with appropriate strategy.

    Selects strategy based on:
    1. Config strategy setting
    2. Backend type (parakeet -> native, faster_whisper -> local_agreement)
    3. Fallback to chunked if needed

    Args:
        session_id: Unique session identifier
        backend: Transcription backend instance
        config: Optional config (uses defaults if None)
        transcription_semaphore: Optional semaphore for GPU serialization

    Returns:
        Configured StreamingSession

    Raises:
        StreamingError: If strategy creation fails

    """
    if config is None:
        config = StreamingConfig.from_config()

    # Determine strategy based on config and backend
    strategy_name = config.strategy
    backend_name = backend.__class__.__name__.lower()

    # Override strategy based on backend if native streaming available
    if "parakeet" in backend_name and _backend_has_native_streaming(backend):
        strategy_name = "native"
        logger.info("Using native strategy for Parakeet backend")
    elif strategy_name == "native" and "parakeet" not in backend_name:
        # Native only works with Parakeet
        logger.warning(
            f"Native strategy requested but backend is {backend_name}, "
            f"falling back to local_agreement"
        )
        strategy_name = "local_agreement"

    # Create strategy
    strategy = _create_strategy(
        strategy_name=strategy_name,
        backend=backend,
        config=config,
        transcription_semaphore=transcription_semaphore,
    )

    # Create and return session
    session = StreamingSession(
        session_id=session_id,
        strategy=strategy,
        config=config,
    )

    logger.info(
        f"Created streaming session {session_id} with {strategy_name} strategy"
    )

    return session


def _backend_has_native_streaming(backend: "TranscriptionBackend") -> bool:
    """Check if backend supports native streaming API."""
    # Check for transcribe_stream method (Parakeet MLX)
    return hasattr(backend, "transcribe_stream") and callable(
        getattr(backend, "transcribe_stream", None)
    )


def _create_strategy(
    strategy_name: str,
    backend: "TranscriptionBackend",
    config: StreamingConfig,
    transcription_semaphore: Optional["asyncio.Semaphore"] = None,
):
    """Create strategy instance based on name.

    Args:
        strategy_name: Name of strategy (local_agreement, chunked, native)
        backend: Backend for batch transcription
        config: Streaming configuration
        transcription_semaphore: Optional semaphore for GPU serialization

    Returns:
        Strategy instance

    """
    import asyncio

    if strategy_name == "local_agreement":
        from .strategies.local_agreement import LocalAgreementStrategy

        # Create batch transcribe function
        async def batch_transcribe(wav_bytes: bytes, prompt: str = "") -> tuple:
            """Async wrapper for backend.transcribe()."""
            import tempfile
            import os

            # Write WAV to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                temp_path = f.name

            try:
                loop = asyncio.get_event_loop()

                # Acquire semaphore if provided (serialize GPU work)
                if transcription_semaphore:
                    async with transcription_semaphore:
                        return await loop.run_in_executor(
                            None,
                            lambda: backend.transcribe(temp_path, language="en"),
                        )
                else:
                    return await loop.run_in_executor(
                        None,
                        lambda: backend.transcribe(temp_path, language="en"),
                    )
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

        return LocalAgreementStrategy(
            batch_transcribe=batch_transcribe,
            config=config,
        )

    if strategy_name == "chunked":
        from .strategies.chunked import ChunkedStrategy

        # Create batch transcribe function (same as above)
        async def batch_transcribe(wav_bytes: bytes, prompt: str = "") -> tuple:
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                temp_path = f.name

            try:
                loop = asyncio.get_event_loop()
                if transcription_semaphore:
                    async with transcription_semaphore:
                        return await loop.run_in_executor(
                            None,
                            lambda: backend.transcribe(temp_path, language="en"),
                        )
                else:
                    return await loop.run_in_executor(
                        None,
                        lambda: backend.transcribe(temp_path, language="en"),
                    )
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

        return ChunkedStrategy(
            batch_transcribe=batch_transcribe,
            config=config,
        )

    if strategy_name == "native":
        from .strategies.native import NativeStrategy

        return NativeStrategy(
            backend=backend,
            config=config,
        )

    raise StreamingError(f"Unknown strategy: {strategy_name}")
