"""Protocol definition for streaming strategies.

Uses Protocol-based typing for flexibility - strategies don't need to inherit
from a base class, just implement the required methods.
"""

from typing import Protocol, runtime_checkable
import numpy as np

from ..types import StreamingResult


@runtime_checkable
class StreamingStrategy(Protocol):
    """Protocol for streaming transcription strategies.

    Strategies process audio chunks and return partial results.
    Different strategies may use different approaches:
    - LocalAgreement: Batch transcription + hypothesis comparison
    - Chunked: Simple periodic batch transcription
    - Native: Wraps native streaming APIs (e.g., Parakeet)

    All strategies must implement:
    - process_audio(): Handle incoming audio chunk
    - finalize(): Complete transcription and flush remaining hypothesis
    - cleanup(): Release resources
    """

    async def process_audio(self, audio_chunk: np.ndarray) -> StreamingResult:
        """Process an audio chunk and return partial result.

        Args:
            audio_chunk: Audio samples (float32, 16kHz mono)

        Returns:
            StreamingResult with confirmed/tentative text
        """
        ...

    async def finalize(self) -> StreamingResult:
        """Finalize transcription and return final result.

        Called when client ends the stream. Should flush any remaining
        hypothesis and return complete transcription.

        Returns:
            Final StreamingResult with is_final=True
        """
        ...

    async def cleanup(self) -> None:
        """Clean up strategy resources.

        Called on session end or abort. Should release any held resources.
        """
        ...
