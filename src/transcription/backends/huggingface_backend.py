"""
HuggingFace Transformers backend for universal ASR model support.

This backend supports any ASR model from HuggingFace Hub, including:
- Whisper variants (openai/whisper-*)
- Wav2Vec2 (facebook/wav2vec2-*)
- Wav2Vec2-BERT (facebook/w2v-bert-2.0)
- HuBERT, WavLM, and many more

Usage in config.json:
    {
        "transcription": {
            "backend": "huggingface"
        },
        "huggingface": {
            "model": "openai/whisper-large-v3",
            "device": "auto",
            "torch_dtype": "auto",
            "chunk_length_s": 30,
            "batch_size": 8
        }
    }
"""

import asyncio
import logging
import tempfile
import time
from typing import Tuple, Optional, Dict, Any

import numpy as np

from .base import TranscriptionBackend
from ...core.config import get_config

logger = logging.getLogger(__name__)
config = get_config()

# Lazy imports - fail gracefully if not installed
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None

try:
    from transformers import pipeline, AutoModelForSpeechSeq2Seq, AutoProcessor
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


def _detect_device() -> str:
    """Auto-detect the best available device."""
    if not TORCH_AVAILABLE:
        return "cpu"

    if torch.cuda.is_available():
        return "cuda:0"

    # Check for Apple Silicon MPS
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"

    return "cpu"


def _resolve_torch_dtype(device: str, dtype_config: str) -> Optional[Any]:
    """Resolve torch dtype based on config and device."""
    if not TORCH_AVAILABLE:
        return None

    if dtype_config == "auto":
        # Use float16 for GPU, float32 for CPU
        if device in ("cpu",):
            return torch.float32
        return torch.float16
    elif dtype_config == "float16":
        return torch.float16
    elif dtype_config == "bfloat16":
        return torch.bfloat16
    elif dtype_config == "float32":
        return torch.float32

    return None  # Let transformers decide


class HuggingFaceBackend(TranscriptionBackend):
    """
    Universal ASR backend using HuggingFace Transformers.

    Supports any model with the 'automatic-speech-recognition' pipeline,
    including Whisper, Wav2Vec2, Wav2Vec2-BERT, HuBERT, and more.

    Advantages:
    - Auto-updates: New HF models work without code changes
    - 17,000+ models: Any ASR model on HuggingFace Hub
    - Device auto-detect: CUDA, MPS (Apple), CPU automatic
    - Caching: HF handles model downloads and caching
    """

    # Default model - good balance of speed and accuracy
    DEFAULT_MODEL = "openai/whisper-base"

    def __init__(self):
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "HuggingFace Transformers is not installed.\n"
                "Install with: pip install transformers torch\n"
                "Or: pip install goobits-stt[huggingface]"
            )

        # Load config with defaults
        hf_config = config.get("huggingface", {}) if hasattr(config, 'get') else {}
        if isinstance(hf_config, type(None)):
            hf_config = {}

        self.model_id = hf_config.get("model", self.DEFAULT_MODEL)
        self.device_config = hf_config.get("device", "auto")
        self.dtype_config = hf_config.get("torch_dtype", "auto")
        self.chunk_length_s = hf_config.get("chunk_length_s", 30)
        self.batch_size = hf_config.get("batch_size", 8)

        # Resolved at load time
        self.device = None
        self.torch_dtype = None
        self.pipe = None

        # Streaming state - uses buffer-based approach with periodic transcription
        self._streaming_buffers: Dict[str, np.ndarray] = {}
        self._streaming_results: Dict[str, str] = {}
        self._streaming_start_times: Dict[str, float] = {}
        self._streaming_sample_counts: Dict[str, int] = {}
        self._streaming_transcribe_interval = 2.0  # Transcribe every 2 seconds of audio

        logger.info(f"HuggingFace backend initialized with model: {self.model_id}")

    async def load(self):
        """Load the ASR model asynchronously."""
        try:
            logger.info(f"Loading HuggingFace ASR model: {self.model_id}")

            # Resolve device
            if self.device_config == "auto":
                self.device = _detect_device()
            else:
                self.device = self.device_config

            # Resolve dtype
            self.torch_dtype = _resolve_torch_dtype(self.device, self.dtype_config)

            logger.info(f"Using device: {self.device}, dtype: {self.torch_dtype}")

            # Load model in executor to avoid blocking
            loop = asyncio.get_event_loop()
            self.pipe = await loop.run_in_executor(None, self._load_pipeline)

            logger.info(f"HuggingFace model {self.model_id} loaded successfully")

        except Exception as e:
            logger.exception(f"Failed to load HuggingFace model: {e}")
            raise

    def _load_pipeline(self):
        """Load the transformers pipeline (blocking call)."""
        # Build pipeline kwargs
        pipe_kwargs = {
            "task": "automatic-speech-recognition",
            "model": self.model_id,
            "device": self.device,
        }

        # Add torch_dtype if available
        if self.torch_dtype is not None:
            pipe_kwargs["torch_dtype"] = self.torch_dtype

        # Create pipeline
        pipe = pipeline(**pipe_kwargs)

        return pipe

    def transcribe(self, audio_path: str, language: str = "en") -> Tuple[str, dict]:
        """
        Transcribe audio using the HuggingFace ASR model.

        Args:
            audio_path: Path to the audio file.
            language: Language code (used for multilingual models like Whisper).

        Returns:
            Tuple of (transcribed_text, metadata_dict).
        """
        if self.pipe is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        start_time = time.time()

        try:
            # Build generation kwargs for multilingual models
            generate_kwargs = {}

            # Check if this is a Whisper model (supports language parameter)
            model_name_lower = self.model_id.lower()
            is_whisper = "whisper" in model_name_lower

            if is_whisper and language:
                generate_kwargs["language"] = language
                # Whisper also supports task parameter
                generate_kwargs["task"] = "transcribe"

            # Run transcription with chunking for long audio
            result = self.pipe(
                audio_path,
                chunk_length_s=self.chunk_length_s,
                batch_size=self.batch_size,
                generate_kwargs=generate_kwargs if generate_kwargs else None,
                return_timestamps=False,  # Simpler output format
            )

            # Extract text from result
            if isinstance(result, dict):
                text = result.get("text", "").strip()
            elif isinstance(result, list):
                # Some models return list of chunks
                text = " ".join(r.get("text", "") for r in result).strip()
            else:
                text = str(result).strip()

            # Calculate processing time
            processing_time = time.time() - start_time

            return text, {
                "duration": processing_time,  # Processing time, not audio duration
                "language": language,
                "backend": "huggingface",
                "model": self.model_id,
                "device": self.device,
            }

        except Exception as e:
            logger.error(f"HuggingFace transcription failed: {e}")
            raise

    @property
    def is_ready(self) -> bool:
        """Check if the model is loaded and ready."""
        return self.pipe is not None

    # ==================== STREAMING IMPLEMENTATION ====================

    @property
    def supports_streaming(self) -> bool:
        """HuggingFace supports streaming via buffer-based chunked transcription."""
        return True

    async def start_streaming(self, session_id: str, **config) -> Dict[str, Any]:
        """
        Start a streaming transcription session.

        Uses buffer-based streaming with periodic transcription since HuggingFace
        pipeline doesn't have native real-time streaming support.
        """
        if session_id in self._streaming_buffers:
            raise RuntimeError(f"Streaming session {session_id} already exists")

        if self.pipe is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Initialize session state
        self._streaming_buffers[session_id] = np.array([], dtype=np.float32)
        self._streaming_results[session_id] = ""
        self._streaming_start_times[session_id] = time.time()
        self._streaming_sample_counts[session_id] = 0

        logger.info(
            f"Started HuggingFace streaming session {session_id} "
            f"(model={self.model_id}, interval={self._streaming_transcribe_interval}s)"
        )

        return {
            "session_id": session_id,
            "ready": True,
            "mode": "buffer-chunked",
            "backend": "huggingface",
            "model": self.model_id,
        }

    async def process_chunk(self, session_id: str, audio_chunk: np.ndarray) -> Dict[str, Any]:
        """
        Process an audio chunk and return partial transcription.

        Accumulates audio and transcribes periodically for efficiency.
        """
        if session_id not in self._streaming_buffers:
            raise RuntimeError(f"No streaming session with ID: {session_id}")

        # Track sample count
        self._streaming_sample_counts[session_id] += len(audio_chunk)

        # Convert int16 to float32 if needed
        if audio_chunk.dtype == np.int16:
            audio_float = audio_chunk.astype(np.float32) / 32768.0
        else:
            audio_float = audio_chunk

        # Accumulate audio
        self._streaming_buffers[session_id] = np.concatenate([
            self._streaming_buffers[session_id],
            audio_float
        ])

        # Transcribe periodically (every N seconds of audio)
        buffer_duration = len(self._streaming_buffers[session_id]) / 16000.0
        should_transcribe = buffer_duration >= self._streaming_transcribe_interval

        if should_transcribe:
            await self._transcribe_buffer(session_id)

        return {
            "text": self._streaming_results.get(session_id, ""),
            "is_final": False,
            "tokens": {
                "finalized": 0,
                "draft": len(self._streaming_results.get(session_id, "").split()),
            },
        }

    async def _transcribe_buffer(self, session_id: str):
        """Transcribe the accumulated buffer for a session."""
        buffer = self._streaming_buffers.get(session_id)
        if buffer is None or len(buffer) == 0:
            return

        try:
            # Save buffer to temp file
            import soundfile as sf
            import os

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                sf.write(temp_path, buffer, 16000)

            # Transcribe using batch method
            text, _ = self.transcribe(temp_path, language="en")
            self._streaming_results[session_id] = text

            # Clean up temp file
            os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Error transcribing buffer for session {session_id}: {e}")

    async def end_streaming(self, session_id: str) -> Dict[str, Any]:
        """
        End a streaming session and return final transcription.
        """
        if session_id not in self._streaming_buffers:
            raise RuntimeError(f"No streaming session with ID: {session_id}")

        try:
            # Final transcription of any remaining audio
            buffer = self._streaming_buffers[session_id]
            text = ""

            if len(buffer) > 0:
                try:
                    import soundfile as sf
                    import os

                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        temp_path = f.name
                        sf.write(temp_path, buffer, 16000)

                    text, _ = self.transcribe(temp_path, language="en")

                    os.unlink(temp_path)
                except Exception as e:
                    logger.error(f"Error in final transcription: {e}")
                    text = self._streaming_results.get(session_id, "")
            else:
                text = self._streaming_results.get(session_id, "")

            # Calculate duration
            sample_count = self._streaming_sample_counts.get(session_id, 0)
            audio_duration = sample_count / 16000.0

            logger.info(
                f"Ended HuggingFace streaming session {session_id}: "
                f"{len(text)} chars, {audio_duration:.2f}s audio"
            )

            return {
                "text": text.strip(),
                "is_final": True,
                "duration": audio_duration,
                "language": "en",
                "backend": "huggingface",
                "model": self.model_id,
            }

        finally:
            # Clean up session state
            self._streaming_buffers.pop(session_id, None)
            self._streaming_results.pop(session_id, None)
            self._streaming_start_times.pop(session_id, None)
            self._streaming_sample_counts.pop(session_id, None)

    @classmethod
    def list_popular_models(cls) -> Dict[str, str]:
        """
        Return a dict of popular ASR models for user reference.

        These are suggestions - any HuggingFace ASR model ID will work.
        """
        return {
            # Whisper models (OpenAI)
            "openai/whisper-tiny": "Fastest, lowest accuracy (~75MB)",
            "openai/whisper-base": "Good balance (~145MB)",
            "openai/whisper-small": "Better accuracy (~490MB)",
            "openai/whisper-medium": "High accuracy (~1.5GB)",
            "openai/whisper-large-v3": "Best accuracy (~3GB)",
            "openai/whisper-large-v3-turbo": "Fast + accurate (~1.6GB)",

            # Distil-Whisper (faster)
            "distil-whisper/distil-large-v3": "6x faster than large-v3",
            "distil-whisper/distil-medium.en": "Fast English-only",

            # Wav2Vec2 models
            "facebook/wav2vec2-base-960h": "Wav2Vec2 base (~380MB)",
            "facebook/wav2vec2-large-960h-lv60-self": "Wav2Vec2 large (~1.2GB)",

            # Wav2Vec2-BERT (2024)
            "facebook/w2v-bert-2.0": "Wav2Vec2-BERT 580M params",

            # Multilingual
            "facebook/mms-1b-all": "1000+ languages",

            # Specialized
            "nvidia/canary-1b": "NVIDIA Canary (multilingual)",
        }
