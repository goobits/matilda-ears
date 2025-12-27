from abc import ABC, abstractmethod
from typing import Tuple


class TranscriptionBackend(ABC):
    """Abstract base class for transcription backends.

    Backends implement batch transcription only. Real-time streaming is handled
    by the streaming framework in src/transcription/streaming/, which wraps
    batch transcription with strategies like LocalAgreement-2.
    """

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
