from abc import ABC, abstractmethod
from typing import Tuple, Dict, Optional, Any
import numpy as np

class TranscriptionBackend(ABC):
    """Abstract base class for transcription backends."""

    @abstractmethod
    async def load(self):
        """Load the model asynchronously."""
        pass

    @abstractmethod
    def transcribe(self, audio_path: str, language: str = "en") -> Tuple[str, dict]:
        """
        Transcribe an audio file.

        Args:
            audio_path: Path to the audio file.
            language: Language code (e.g., "en").

        Returns:
            A tuple containing:
            - The transcribed text.
            - A dictionary with metadata (e.g., duration, language).
        """
        pass

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """Check if the backend is ready/loaded."""
        pass

    # ==================== STREAMING INTERFACE (Optional) ====================
    # Subclasses can override these to enable real-time streaming transcription.
    # Default implementations raise NotImplementedError for backward compatibility.

    @property
    def supports_streaming(self) -> bool:
        """
        Whether this backend supports real-time streaming transcription.

        Override to return True if the backend implements streaming methods.
        Default is False for backward compatibility with batch-only backends.
        """
        return False

    async def start_streaming(self, session_id: str, **config) -> Dict[str, Any]:
        """
        Start a streaming transcription session.

        Args:
            session_id: Unique identifier for this streaming session.
            **config: Backend-specific configuration options.

        Returns:
            Dict with session info: {"session_id": str, "ready": bool, ...}

        Raises:
            NotImplementedError: If streaming is not supported.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support streaming. "
            "Check supports_streaming property before calling."
        )

    async def process_chunk(self, session_id: str, audio_chunk: np.ndarray) -> Dict[str, Any]:
        """
        Process an audio chunk and return partial transcription result.

        Args:
            session_id: Session ID from start_streaming().
            audio_chunk: Audio data as numpy array (int16 or float32, 16kHz mono).

        Returns:
            Dict with partial result: {
                "text": str,           # Current transcription
                "is_final": bool,      # Always False for partial results
                "tokens": {            # Optional token-level info
                    "finalized": int,  # Stable tokens
                    "draft": int       # Provisional tokens
                }
            }

        Raises:
            NotImplementedError: If streaming is not supported.
            RuntimeError: If no active session with given ID.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support streaming. "
            "Check supports_streaming property before calling."
        )

    async def end_streaming(self, session_id: str) -> Dict[str, Any]:
        """
        End a streaming session and return the final transcription.

        Args:
            session_id: Session ID from start_streaming().

        Returns:
            Dict with final result: {
                "text": str,           # Final transcription
                "is_final": True,
                "duration": float,     # Audio duration in seconds
                "language": str,       # Detected/used language
                "backend": str         # Backend name
            }

        Raises:
            NotImplementedError: If streaming is not supported.
            RuntimeError: If no active session with given ID.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support streaming. "
            "Check supports_streaming property before calling."
        )
