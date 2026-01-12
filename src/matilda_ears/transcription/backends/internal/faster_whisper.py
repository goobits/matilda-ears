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
        config = get_config()
        self.model_size = config.whisper_model
        self.device = config.whisper_device_auto
        self.compute_type = config.whisper_compute_type_auto
        self.word_timestamps = config.get("whisper.word_timestamps", True)

        # VAD configuration (critical for preventing hallucinations on silence)
        self.vad_filter = config.get("whisper.vad_filter", True)
        self.vad_parameters = config.get(
            "whisper.vad_parameters",
            {
                "threshold": 0.5,
                "min_speech_duration_ms": 250,
                "max_speech_duration_s": 30,
                "min_silence_duration_ms": 200,
            },
        )

        # Hallucination suppression
        self.no_speech_threshold = config.get("whisper.no_speech_threshold", 0.6)

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
            vad_filter=self.vad_filter,
            vad_parameters=self.vad_parameters,
            no_speech_threshold=self.no_speech_threshold,
        )

        # Collect segments and extract word timestamps
        all_segments = list(segments)
        text = "".join([segment.text for segment in all_segments]).strip()

        # Extract word-level timestamps for LocalAgreement streaming
        words = []
        if self.word_timestamps:
            for segment in all_segments:
                word_items = getattr(segment, "words", None)
                if not word_items:
                    continue
                try:
                    for word in word_items:
                        words.append(
                            {
                                "word": word.word,
                                "start": word.start,
                                "end": word.end,
                                "probability": word.probability,
                            }
                        )
                except TypeError:
                    logger.debug("Skipping non-iterable word timestamps")

        return text, {
            "duration": info.duration,
            "language": info.language,
            "words": words,
        }

    @property
    def is_ready(self) -> bool:
        return self.model is not None
