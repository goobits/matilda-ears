#!/usr/bin/env python3
"""Silero Voice Activity Detection (VAD) module

Provides accurate voice activity detection using the Silero VAD model.
Significantly more accurate than simple amplitude-based detection.
"""

from typing import List, Tuple, Any, Optional
import asyncio
import logging

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    # Create a dummy numpy module for type annotations
    class _DummyNumpy:
        class ndarray:
            pass
    np = _DummyNumpy()

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class SileroVAD:
    """Voice Activity Detection using Silero VAD model.

    Supports 8kHz and 16kHz sample rates with real-time performance.
    Processes 30ms+ chunks in <1ms on CPU.
    """

    def __init__(self,
                 sample_rate: int = 16000,
                 threshold: float = 0.5,
                 min_speech_duration: float = 0.25,
                 min_silence_duration: float = 0.5,
                 padding_duration: float = 0.3,
                 use_onnx: bool = True):
        """Initialize Silero VAD.

        Args:
            sample_rate: Audio sample rate (8000 or 16000 Hz)
            threshold: Speech detection threshold (0.0-1.0)
            min_speech_duration: Minimum speech duration in seconds
            min_silence_duration: Minimum silence duration to end speech
            padding_duration: Padding to add before/after speech segments
            use_onnx: Use ONNX model for 4-5x faster inference

        """
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_duration = min_speech_duration
        self.min_silence_duration = min_silence_duration
        self.padding_duration = padding_duration
        self.use_onnx = use_onnx

        # Check dependencies
        if not NUMPY_AVAILABLE:
            raise ImportError(
                "NumPy is required for VAD. "
                "Install with: pip install numpy"
            )

        if not TORCH_AVAILABLE:
            raise ImportError(
                "PyTorch is required for Silero VAD. "
                "Install with: pip install torch torchaudio"
            )

        # Validate sample rate
        if sample_rate not in [8000, 16000]:
            raise ValueError(f"Sample rate must be 8000 or 16000 Hz, got {sample_rate}")

        # Model state
        self.model = None
        self.utils = None

        # VAD state
        self.speech_timestamps: list[dict[str, Any]] = []
        self.current_speech_start: Optional[int] = None
        self.temp_end = 0
        self.triggered = False

        # Setup logging
        self.logger = logging.getLogger(__name__)

        # Load model
        self._load_model()

    def _load_model(self):
        """Load Silero VAD model from torch hub."""
        try:
            # Set single thread for real-time performance
            torch.set_num_threads(1)

            self.logger.info(f"Loading Silero VAD model (ONNX: {self.use_onnx})...")

            # Try the newer silero-vad package first
            try:
                from silero_vad import load_silero_vad, get_speech_timestamps
                self.model = load_silero_vad(onnx=self.use_onnx)
                self.get_speech_timestamps = get_speech_timestamps
                self.logger.info("Loaded Silero VAD using silero-vad package")
                return
            except ImportError:
                self.logger.debug("silero-vad package not available, using torch.hub")

            # Fallback to torch.hub method
            self.model, self.utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=self.use_onnx,
                verbose=False
            )

            # Get utility functions from torch.hub
            if self.utils is not None:
                (get_speech_timestamps, _, _, _, _) = self.utils
                self.get_speech_timestamps = get_speech_timestamps
            else:
                raise RuntimeError("Utils not loaded from torch.hub")

            self.logger.info("Silero VAD model loaded successfully via torch.hub")

        except Exception as e:
            self.logger.error(f"Failed to load Silero VAD model: {e}")
            # Provide helpful error message
            error_msg = (
                f"Failed to load VAD model: {e}. "
                "Make sure you have installed: pip install torch torchaudio silero-vad"
            )
            raise RuntimeError(error_msg)

    def process_chunk(self, audio_chunk: np.ndarray) -> float:
        """Process a single audio chunk and return speech probability.

        Args:
            audio_chunk: Audio data as numpy array (int16 or float32)

        Returns:
            Speech probability (0.0-1.0)

        """
        try:
            # Convert to float32 if needed
            if audio_chunk.dtype == np.int16:
                audio_float = audio_chunk.astype(np.float32) / 32768.0
            else:
                audio_float = audio_chunk.astype(np.float32)

            # Ensure 1D array
            audio_float = audio_float.squeeze()

            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio_float)

            # Get speech probability
            if self.model is None:
                raise RuntimeError("Model not loaded")
            with torch.no_grad():
                speech_prob = self.model(audio_tensor, self.sample_rate).item()

            return float(speech_prob)

        except Exception as e:
            self.logger.error(f"Error processing audio chunk: {e}")
            return 0.0

    def process_chunk_with_state(self, audio_chunk: np.ndarray,
                                chunk_length_ms: int = 100) -> Tuple[float, str]:
        """Process chunk with state machine for robust speech detection.

        Args:
            audio_chunk: Audio data
            chunk_length_ms: Length of chunk in milliseconds

        Returns:
            Tuple of (speech_probability, state) where state is:
            - 'silence': No speech detected
            - 'speech_start': Speech just started
            - 'speech': Ongoing speech
            - 'speech_end': Speech just ended

        """
        speech_prob = self.process_chunk(audio_chunk)
        state = "silence"

        # Convert durations to chunk counts
        chunks_per_second = 1000 / chunk_length_ms
        min_speech_chunks = int(self.min_speech_duration * chunks_per_second)
        min_silence_chunks = int(self.min_silence_duration * chunks_per_second)

        # Update state machine
        if speech_prob >= self.threshold:
            if not self.triggered:
                self.triggered = True
                self.current_speech_start = int(self.temp_end)
                state = "speech_start"
            else:
                state = "speech"
            self.temp_end += 1

        else:
            if self.triggered:
                if self.current_speech_start is not None and (self.temp_end - self.current_speech_start) < min_speech_chunks:
                    # Too short, reset
                    self.triggered = False
                    self.current_speech_start = None
                    state = "silence"
                elif self.current_speech_start is not None and (self.temp_end - self.current_speech_start) >= min_silence_chunks:
                    # Speech ended
                    self.speech_timestamps.append({
                        "start": self.current_speech_start,
                        "end": self.temp_end - min_silence_chunks
                    })
                    self.triggered = False
                    self.current_speech_start = None
                    state = "speech_end"
                else:
                    state = "speech"  # Still in speech, just a brief pause
            else:
                state = "silence"
            self.temp_end += 1

        return speech_prob, state

    def reset_states(self):
        """Reset VAD state machine."""
        self.speech_timestamps = []
        self.current_speech_start = None
        self.temp_end = 0
        self.triggered = False

    def process_audio_buffer(self, audio_buffer: np.ndarray) -> List[dict]:
        """Process entire audio buffer and return speech segments.

        Args:
            audio_buffer: Complete audio data

        Returns:
            List of speech segments with start/end times in seconds

        """
        try:
            # Convert to float32 if needed
            if audio_buffer.dtype == np.int16:
                audio_float = audio_buffer.astype(np.float32) / 32768.0
            else:
                audio_float = audio_buffer.astype(np.float32)

            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio_float)

            # Get speech timestamps
            speech_timestamps = self.get_speech_timestamps(
                audio_tensor,
                self.model,
                sampling_rate=self.sample_rate,
                threshold=self.threshold,
                min_speech_duration_ms=int(self.min_speech_duration * 1000),
                min_silence_duration_ms=int(self.min_silence_duration * 1000),
                speech_pad_ms=int(self.padding_duration * 1000),
                return_seconds=True
            )

            return list(speech_timestamps)

        except Exception as e:
            self.logger.error(f"Error processing audio buffer: {e}")
            return []

    async def process_chunk_async(self, audio_chunk: np.ndarray) -> float:
        """Async wrapper for process_chunk."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.process_chunk, audio_chunk)

    def get_stats(self) -> dict:
        """Get VAD statistics."""
        return {
            "sample_rate": self.sample_rate,
            "threshold": self.threshold,
            "model_type": "ONNX" if self.use_onnx else "JIT",
            "speech_segments": len(self.speech_timestamps),
            "is_speaking": self.triggered
        }


class VADProcessor:
    """High-level VAD processor with buffering and smoothing.
    """

    def __init__(self, vad: SileroVAD, buffer_size: int = 3):
        """Initialize VAD processor.

        Args:
            vad: SileroVAD instance
            buffer_size: Number of chunks to buffer for smoothing

        """
        self.vad = vad
        self.buffer_size = buffer_size
        self.prob_buffer: list[float] = []
        self.logger = logging.getLogger(__name__)

    def process_with_smoothing(self, audio_chunk: np.ndarray) -> Tuple[float, float]:
        """Process chunk with probability smoothing.

        Returns:
            Tuple of (instant_probability, smoothed_probability)

        """
        # Get instant probability
        instant_prob = self.vad.process_chunk(audio_chunk)

        # Add to buffer
        self.prob_buffer.append(instant_prob)
        if len(self.prob_buffer) > self.buffer_size:
            self.prob_buffer.pop(0)

        # Calculate smoothed probability
        smoothed_prob = np.mean(self.prob_buffer)

        return instant_prob, smoothed_prob

    def is_speech(self, smoothed_prob: float,
                  aggressive: bool = False) -> bool:
        """Determine if audio contains speech.

        Args:
            smoothed_prob: Smoothed speech probability
            aggressive: Use more aggressive thresholds

        Returns:
            True if speech detected

        """
        threshold = self.vad.threshold
        if aggressive:
            threshold = min(0.7, threshold + 0.15)

        return smoothed_prob >= threshold


class SimpleFallbackVAD:
    """Simple amplitude-based VAD fallback when Silero is not available.

    This provides basic functionality using RMS amplitude detection
    as a fallback when PyTorch/Silero dependencies are not installed.
    """

    def __init__(self,
                 sample_rate: int = 16000,
                 threshold: float = 0.01,
                 **kwargs):
        """Initialize simple VAD with amplitude threshold."""
        if not NUMPY_AVAILABLE:
            raise ImportError(
                "NumPy is required for VAD. "
                "Install with: pip install numpy"
            )

        self.sample_rate = sample_rate
        self.threshold = threshold
        self.logger = logging.getLogger(__name__)

        self.logger.warning(
            "Using fallback amplitude-based VAD. "
            "For better accuracy, install: pip install torch torchaudio silero-vad"
        )

    def process_chunk(self, audio_chunk: np.ndarray) -> float:
        """Process chunk with simple RMS amplitude detection.

        Returns RMS normalized to 0-1 range (approximates speech probability).
        """
        try:
            # Convert to float32 if needed
            if audio_chunk.dtype == np.int16:
                audio_float = audio_chunk.astype(np.float32) / 32768.0
            else:
                audio_float = audio_chunk.astype(np.float32)

            # Calculate RMS
            rms = np.sqrt(np.mean(audio_float ** 2))

            # Normalize to approximate probability
            # This is a rough approximation, not real speech detection
            normalized_prob = min(1.0, rms / self.threshold * 0.5)

            return float(normalized_prob)

        except Exception as e:
            self.logger.error(f"Error in fallback VAD: {e}")
            return 0.0

    def get_stats(self) -> dict:
        """Get VAD statistics."""
        return {
            "sample_rate": self.sample_rate,
            "threshold": self.threshold,
            "model_type": "Fallback_RMS",
            "speech_segments": 0,
            "is_speaking": False
        }

    def reset_states(self):
        """Reset VAD state (no-op for simple VAD)."""


def create_vad(sample_rate: int = 16000,
               threshold: float = 0.5,
               use_fallback: bool = False,
               **kwargs):
    """Create the best available VAD instance.

    Args:
        sample_rate: Audio sample rate
        threshold: Speech detection threshold
        use_fallback: Force use of simple fallback VAD
        **kwargs: Additional arguments for VAD initialization

    Returns:
        VAD instance (SileroVAD or SimpleFallbackVAD)

    Raises:
        ImportError: If required dependencies are not available

    """
    # Check minimum dependencies
    if not NUMPY_AVAILABLE:
        raise ImportError(
            "NumPy is required for VAD functionality. "
            "Install with: pip install numpy"
        )

    if use_fallback or not TORCH_AVAILABLE:
        return SimpleFallbackVAD(
            sample_rate=sample_rate,
            threshold=threshold * 20,  # Scale threshold for RMS
            **kwargs
        )

    try:
        return SileroVAD(
            sample_rate=sample_rate,
            threshold=threshold,
            **kwargs
        )
    except Exception as e:
        logging.getLogger(__name__).warning(
            f"Failed to create SileroVAD ({e}), falling back to simple VAD"
        )
        return SimpleFallbackVAD(
            sample_rate=sample_rate,
            threshold=threshold * 20,  # Scale threshold for RMS
            **kwargs
        )
