import asyncio
import logging

from ..base import TranscriptionBackend
from ....core.config import get_config

logger = logging.getLogger(__name__)


class FasterWhisperBackend(TranscriptionBackend):
    """Backend implementation using faster-whisper for batch transcription.

    Real-time streaming is handled by the streaming framework, which uses
    this backend's transcribe() method with LocalAgreement-2.
    """

    def __init__(self):
        from .. import faster_whisper_backend as wrapper

        config = wrapper.config if hasattr(wrapper, "config") else get_config()
        self.model_size = config.whisper_model
        self.device = config.whisper_device_auto
        self.compute_type = config.whisper_compute_type_auto
        self.word_timestamps = config.get("whisper.word_timestamps", True)
        self.model = None

    async def load(self):
        """Load Faster Whisper model asynchronously."""
        try:
            from faster_whisper import WhisperModel

            logger.info(f"Loading Faster Whisper {self.model_size} model on {self.device} with {self.compute_type}...")
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None, lambda: WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
            )
            logger.info(f"Faster Whisper {self.model_size} model loaded successfully")
        except ImportError:
            raise ImportError("faster-whisper is not installed. Please install it or use a different backend.")
        except Exception as e:
            logger.exception(f"Failed to load Faster Whisper model: {e}")
            raise

    def transcribe(self, audio_path: str, language: str = "en") -> tuple[str, dict]:
        if self.model is None:
            raise RuntimeError("Model not loaded")

        segments, info = self.model.transcribe(
            audio_path,
            beam_size=5,
            language=language,
            word_timestamps=self.word_timestamps,
        )
        text = "".join([segment.text for segment in segments]).strip()

        return text, {
            "duration": info.duration,
            "language": info.language,
        }

    @property
    def is_ready(self) -> bool:
        return self.model is not None
