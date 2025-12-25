import asyncio
import logging
import time
from typing import Tuple, Dict, Any, Optional

import numpy as np

from .base import TranscriptionBackend
from ...core.config import get_config

logger = logging.getLogger(__name__)
config = get_config()

# Check if whisper-streaming is available for real-time streaming
WHISPER_STREAMING_AVAILABLE = False
try:
    from whisper_online import FasterWhisperASR, OnlineASRProcessor
    WHISPER_STREAMING_AVAILABLE = True
except ImportError:
    logger.debug("whisper-streaming not installed. Streaming will use fallback mode.")


class FasterWhisperBackend(TranscriptionBackend):
    """Backend implementation using faster-whisper with optional streaming support."""

    def __init__(self):
        self.model_size = config.whisper_model
        self.device = config.whisper_device_auto
        self.compute_type = config.whisper_compute_type_auto
        self.model = None

        # Streaming configuration
        self._streaming_chunk_size = config.get("whisper.streaming.chunk_size", 1.0)  # seconds
        self._streaming_buffer_trimming = config.get(
            "whisper.streaming.buffer_trimming", ("segment", 15)
        )

        # Streaming state
        self._streaming_asr: Optional[Any] = None  # Shared FasterWhisperASR instance
        self._streaming_processors: Dict[str, Any] = {}  # session_id -> OnlineASRProcessor
        self._streaming_buffers: Dict[str, np.ndarray] = {}  # Accumulated audio per session
        self._streaming_results: Dict[str, str] = {}  # Current transcription per session
        self._streaming_start_times: Dict[str, float] = {}
        self._streaming_sample_counts: Dict[str, int] = {}

    async def load(self):
        """Load Faster Whisper model asynchronously."""
        try:
            from faster_whisper import WhisperModel
            
            logger.info(f"Loading Faster Whisper {self.model_size} model on {self.device} with {self.compute_type}...")
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                lambda: WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
            )
            logger.info(f"Faster Whisper {self.model_size} model loaded successfully")
        except ImportError:
            raise ImportError("faster-whisper is not installed. Please install it or use a different backend.")
        except Exception as e:
            logger.exception(f"Failed to load Faster Whisper model: {e}")
            raise

    def transcribe(self, audio_path: str, language: str = "en") -> Tuple[str, dict]:
        if self.model is None:
            raise RuntimeError("Model not loaded")

        segments, info = self.model.transcribe(audio_path, beam_size=5, language=language)
        text = "".join([segment.text for segment in segments]).strip()

        return text, {
            "duration": info.duration,
            "language": info.language,
        }

    @property
    def is_ready(self) -> bool:
        return self.model is not None

    # ==================== STREAMING IMPLEMENTATION ====================

    @property
    def supports_streaming(self) -> bool:
        """
        Streaming is supported if whisper-streaming library is installed.
        Falls back to buffer-based streaming if not available.
        """
        return True  # We support streaming with or without whisper-streaming

    def _ensure_streaming_asr(self):
        """Lazily initialize the shared FasterWhisperASR instance."""
        if self._streaming_asr is not None:
            return

        if not WHISPER_STREAMING_AVAILABLE:
            logger.info("whisper-streaming not available, using buffer-based fallback")
            return

        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        try:
            # Create FasterWhisperASR wrapper around our loaded model
            # Note: FasterWhisperASR can use an existing model or load its own
            self._streaming_asr = FasterWhisperASR(
                lan="en",
                modelsize=self.model_size,
            )
            # Enable VAD for better streaming performance
            self._streaming_asr.use_vad()
            logger.info(f"Initialized FasterWhisperASR for streaming (model={self.model_size})")
        except Exception as e:
            logger.warning(f"Failed to initialize FasterWhisperASR: {e}. Using fallback mode.")
            self._streaming_asr = None

    async def start_streaming(self, session_id: str, **config) -> Dict[str, Any]:
        """
        Start a streaming transcription session.

        Uses whisper-streaming library if available, otherwise falls back to
        buffer-based streaming that transcribes periodically.
        """
        if session_id in self._streaming_processors or session_id in self._streaming_buffers:
            raise RuntimeError(f"Streaming session {session_id} already exists")

        if self.model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Try to initialize whisper-streaming ASR
        self._ensure_streaming_asr()

        self._streaming_start_times[session_id] = time.time()
        self._streaming_sample_counts[session_id] = 0
        self._streaming_results[session_id] = ""

        if WHISPER_STREAMING_AVAILABLE and self._streaming_asr is not None:
            # Use whisper-streaming for real-time transcription
            try:
                processor = OnlineASRProcessor(
                    asr=self._streaming_asr,
                    buffer_trimming=self._streaming_buffer_trimming,
                )
                self._streaming_processors[session_id] = processor

                logger.info(f"Started Whisper streaming session {session_id} (whisper-streaming mode)")

                return {
                    "session_id": session_id,
                    "ready": True,
                    "mode": "whisper-streaming",
                    "backend": "faster_whisper",
                }
            except Exception as e:
                logger.warning(f"Failed to create OnlineASRProcessor: {e}. Using fallback.")

        # Fallback: buffer-based streaming
        self._streaming_buffers[session_id] = np.array([], dtype=np.float32)

        logger.info(f"Started Whisper streaming session {session_id} (buffer fallback mode)")

        return {
            "session_id": session_id,
            "ready": True,
            "mode": "buffer-fallback",
            "backend": "faster_whisper",
        }

    async def process_chunk(self, session_id: str, audio_chunk: np.ndarray) -> Dict[str, Any]:
        """
        Process an audio chunk and return partial transcription.
        """
        if session_id not in self._streaming_processors and session_id not in self._streaming_buffers:
            raise RuntimeError(f"No streaming session with ID: {session_id}")

        # Track sample count
        self._streaming_sample_counts[session_id] += len(audio_chunk)

        # Convert int16 to float32 if needed (whisper-streaming expects float32)
        if audio_chunk.dtype == np.int16:
            audio_float = audio_chunk.astype(np.float32) / 32768.0
        else:
            audio_float = audio_chunk

        # Try whisper-streaming mode first
        if session_id in self._streaming_processors:
            return await self._process_chunk_whisper_streaming(session_id, audio_float)

        # Fallback: buffer-based mode
        return await self._process_chunk_buffer_fallback(session_id, audio_float)

    async def _process_chunk_whisper_streaming(
        self, session_id: str, audio_chunk: np.ndarray
    ) -> Dict[str, Any]:
        """Process chunk using whisper-streaming library."""
        processor = self._streaming_processors[session_id]

        try:
            # Insert audio chunk
            processor.insert_audio_chunk(audio_chunk)

            # Process and get output
            # Returns: (beg_timestamp, end_timestamp, "text") or (None, None, "")
            output = processor.process_iter()

            # Check if there's newly confirmed text (timestamp is not None)
            if output[0] is not None:
                # Accumulate the INCREMENTAL confirmed text
                delta_text = output[2]
                if delta_text:
                    if self._streaming_results[session_id]:
                        self._streaming_results[session_id] += " " + delta_text
                    else:
                        self._streaming_results[session_id] = delta_text

            return {
                "text": self._streaming_results[session_id],
                "is_final": False,
                "tokens": {
                    "finalized": len(self._streaming_results[session_id].split()),
                    "draft": 0,
                },
            }

        except Exception as e:
            logger.error(f"Error in whisper-streaming processing: {e}")
            return {
                "text": self._streaming_results.get(session_id, ""),
                "is_final": False,
                "error": str(e),
            }

    async def _process_chunk_buffer_fallback(
        self, session_id: str, audio_chunk: np.ndarray
    ) -> Dict[str, Any]:
        """
        Fallback streaming: accumulate audio and transcribe periodically.

        This is less real-time but works without whisper-streaming library.
        """
        # Accumulate audio
        self._streaming_buffers[session_id] = np.concatenate([
            self._streaming_buffers[session_id],
            audio_chunk
        ])

        # Transcribe every ~2 seconds of accumulated audio (32000 samples at 16kHz)
        buffer_samples = len(self._streaming_buffers[session_id])
        transcribe_threshold = 32000  # 2 seconds

        if buffer_samples >= transcribe_threshold:
            try:
                # Save buffer to temp file for transcription
                import tempfile
                import soundfile as sf

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    temp_path = f.name
                    sf.write(temp_path, self._streaming_buffers[session_id], 16000)

                # Transcribe
                text, _ = self.transcribe(temp_path, language="en")
                self._streaming_results[session_id] = text

                # Clean up
                import os
                os.unlink(temp_path)

            except Exception as e:
                logger.error(f"Error in buffer fallback transcription: {e}")

        return {
            "text": self._streaming_results.get(session_id, ""),
            "is_final": False,
            "tokens": {
                "finalized": 0,
                "draft": len(self._streaming_results.get(session_id, "").split()),
            },
        }

    async def end_streaming(self, session_id: str) -> Dict[str, Any]:
        """
        End a streaming session and return final transcription.
        """
        has_processor = session_id in self._streaming_processors
        has_buffer = session_id in self._streaming_buffers

        if not has_processor and not has_buffer:
            raise RuntimeError(f"No streaming session with ID: {session_id}")

        try:
            text = ""

            if has_processor:
                # Finalize whisper-streaming processor
                processor = self._streaming_processors[session_id]
                try:
                    # finish() returns (beg_timestamp, end_timestamp, "text") or (None, None, "")
                    final_output = processor.finish()
                    if final_output[0] is not None and final_output[2]:
                        # Append final unconfirmed text
                        if self._streaming_results[session_id]:
                            self._streaming_results[session_id] += " " + final_output[2]
                        else:
                            self._streaming_results[session_id] = final_output[2]
                except Exception as e:
                    logger.warning(f"Error finalizing processor: {e}")

                text = self._streaming_results.get(session_id, "")

            elif has_buffer:
                # Final transcription of accumulated buffer
                buffer = self._streaming_buffers[session_id]
                if len(buffer) > 0:
                    try:
                        import tempfile
                        import soundfile as sf

                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                            temp_path = f.name
                            sf.write(temp_path, buffer, 16000)

                        text, _ = self.transcribe(temp_path, language="en")

                        import os
                        os.unlink(temp_path)
                    except Exception as e:
                        logger.error(f"Error in final transcription: {e}")
                        text = self._streaming_results.get(session_id, "")

            # Calculate duration
            sample_count = self._streaming_sample_counts.get(session_id, 0)
            audio_duration = sample_count / 16000.0

            logger.info(
                f"Ended Whisper streaming session {session_id}: "
                f"{len(text)} chars, {audio_duration:.2f}s audio"
            )

            return {
                "text": text.strip(),
                "is_final": True,
                "duration": audio_duration,
                "language": "en",
                "backend": "faster_whisper",
            }

        finally:
            # Clean up session state
            self._streaming_processors.pop(session_id, None)
            self._streaming_buffers.pop(session_id, None)
            self._streaming_results.pop(session_id, None)
            self._streaming_start_times.pop(session_id, None)
            self._streaming_sample_counts.pop(session_id, None)
