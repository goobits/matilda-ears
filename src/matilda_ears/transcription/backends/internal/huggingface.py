"""HuggingFace Transformers backend for universal ASR model support.

This backend supports any ASR model from HuggingFace Hub, including:
- Whisper variants (openai/whisper-*)
- Wav2Vec2 (facebook/wav2vec2-*)
- Wav2Vec2-BERT (facebook/w2v-bert-2.0)
- HuBERT, WavLM, and many more

Real-time streaming is handled by the streaming framework in
src/transcription/streaming/, which wraps batch transcription.

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
import time
from typing import Tuple, Optional, Any, Dict

from ..base import TranscriptionBackend
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
    if dtype_config == "float16":
        return torch.float16
    if dtype_config == "bfloat16":
        return torch.bfloat16
    if dtype_config == "float32":
        return torch.float32

    return None  # Let transformers decide


class HuggingFaceBackend(TranscriptionBackend):
    """Universal ASR backend using HuggingFace Transformers.

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
                "Or: pip install goobits-matilda-ears[huggingface]"
            )

        # Load config with defaults
        hf_config = config.get("huggingface", {}) if hasattr(config, "get") else {}
        if hf_config is None:
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
        """Transcribe audio using the HuggingFace ASR model.

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
                # Prevent repetition hallucinations (common Whisper issue)
                generate_kwargs["no_repeat_ngram_size"] = 3
                generate_kwargs["repetition_penalty"] = 1.2

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

            # Post-process: Remove obvious repetitions (Whisper hallucination artifact)
            text = self._remove_repetitions(text)

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

    def _remove_repetitions(self, text: str, min_phrase_len: int = 3, max_repeats: int = 2) -> str:
        """Remove obvious repetition patterns from transcription.

        Whisper can hallucinate repeated phrases when audio has silence or is unclear.
        This detects patterns like "Hello? Hello? Hello? Hello?" and reduces them.

        Args:
            text: Input text to clean
            min_phrase_len: Minimum words in a phrase to consider for deduplication
            max_repeats: Maximum times a phrase should appear

        Returns:
            Cleaned text with repetitions removed

        """
        if not text:
            return text

        words = text.split()
        if len(words) < min_phrase_len * 2:
            return text

        # Try different phrase lengths (3-8 words)
        for phrase_len in range(min_phrase_len, min(9, len(words) // 2)):
            cleaned_words = []
            i = 0
            while i < len(words):
                phrase = words[i:i + phrase_len]
                if len(phrase) < phrase_len:
                    cleaned_words.extend(phrase)
                    break

                # Count consecutive repetitions of this phrase
                repeat_count = 1
                j = i + phrase_len
                while j + phrase_len <= len(words):
                    next_phrase = words[j:j + phrase_len]
                    if next_phrase == phrase:
                        repeat_count += 1
                        j += phrase_len
                    else:
                        break

                # If too many repetitions, keep only max_repeats
                if repeat_count > max_repeats:
                    logger.warning(
                        f"Detected repetition: '{' '.join(phrase)}' x{repeat_count}, "
                        f"reducing to x{max_repeats}"
                    )
                    for _ in range(max_repeats):
                        cleaned_words.extend(phrase)
                    i = j  # Skip all repetitions
                else:
                    cleaned_words.append(words[i])
                    i += 1

            # If we removed something, update words and continue checking
            if len(cleaned_words) < len(words):
                words = cleaned_words

        return " ".join(words)

    @classmethod
    def list_popular_models(cls) -> Dict[str, str]:
        """Return a dict of popular ASR models for user reference.

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
