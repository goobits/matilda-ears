#!/usr/bin/env python3
"""
Conversation Mode - Continuous VAD-based listening for hands-free operation

This mode enables continuous, hands-free listening with:
- Voice Activity Detection (VAD) to detect speech
- Automatic transcription of each utterance
- Immediate return to listening state after transcription
- Interruption support for new speech while processing
"""

import asyncio
import threading
import time
import json
from typing import Dict, Any
from pathlib import Path
import sys

# Add project root to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.absolute()))

from src.core.config import get_config, setup_logging
from src.audio.capture import PipeBasedAudioStreamer

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    # Create dummy for type annotations
    class _DummyNumpy:
        class ndarray:
            pass
    np = _DummyNumpy()


class ConversationMode:
    """Continuous conversation mode with VAD-based utterance detection."""

    def __init__(self, args):
        self.args = args
        self.config = get_config()
        self.logger = setup_logging(__name__,
                                  log_level="DEBUG" if args.debug else "INFO",
                                  include_console=args.format != "json",
                                  include_file=True)

        # Audio processing
        self.audio_queue = None
        self.audio_streamer = None
        self.loop = None

        # VAD and transcription
        self.is_listening = False
        self.is_processing = False
        self.current_utterance = []
        self.vad = None  # Silero VAD instance
        self.vad_threshold = 0.5  # Speech probability threshold
        self.min_speech_duration = 0.5  # Minimum speech duration in seconds
        self.max_silence_duration = 1.0  # Maximum silence before utterance end
        self.speech_pad_duration = 0.3  # Padding before/after speech

        # VAD state machine
        self.vad_state = "silence"  # silence, speech, trailing
        self.consecutive_speech = 0
        self.consecutive_silence = 0
        self.chunks_per_second = 10  # 100ms chunks

        # Whisper model
        self.model = None

        # Threading
        self.processing_thread = None
        self.stop_event = threading.Event()

        # Check dependencies
        if not NUMPY_AVAILABLE:
            raise ImportError(
                "NumPy is required for conversation mode. "
                "Install with: pip install numpy"
            )

        self.logger.info("Conversation mode initialized")

    async def run(self):
        """Main conversation mode loop."""
        try:
            # Initialize Whisper model
            await self._load_model()

            # Initialize VAD
            await self._initialize_vad()

            # Start audio streaming
            await self._start_audio_streaming()

            # Send initial status
            await self._send_status("listening", "Conversation mode active - speak naturally")

            # Main processing loop
            await self._conversation_loop()

        except KeyboardInterrupt:
            await self._send_status("interrupted", "Conversation mode stopped by user")
        except Exception as e:
            self.logger.exception(f"Conversation mode error: {e}")
            await self._send_error(f"Conversation mode failed: {e}")
        finally:
            await self._cleanup()

    async def _load_model(self):
        """Load Whisper model asynchronously."""
        try:
            from faster_whisper import WhisperModel

            self.logger.info(f"Loading Whisper model: {self.args.model}")

            # Load in executor to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None, lambda: WhisperModel(self.args.model, device="cpu", compute_type="int8")
            )

            self.logger.info(f"Whisper model {self.args.model} loaded successfully")

        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
            raise

    async def _initialize_vad(self):
        """Initialize Silero VAD in executor to avoid blocking."""
        try:
            from src.audio.vad import SileroVAD
            self.logger.info("Initializing Silero VAD...")

            loop = asyncio.get_event_loop()
            self.vad = await loop.run_in_executor(
                None,
                lambda: SileroVAD(
                    sample_rate=self.args.sample_rate,
                    threshold=self.vad_threshold,
                    min_speech_duration=self.min_speech_duration,
                    min_silence_duration=self.max_silence_duration,
                    use_onnx=True  # Faster inference
                )
            )

            self.logger.info("Silero VAD initialized successfully")
        except ImportError as e:
            self.logger.error(f"VAD dependencies not available: {e}")
            self.logger.error("Install dependencies with: pip install torch torchaudio silero-vad")
            raise RuntimeError(f"VAD initialization failed: {e}")
        except Exception as e:
            self.logger.error(f"Failed to initialize VAD: {e}")
            raise

    async def _start_audio_streaming(self):
        """Initialize audio streaming."""
        try:
            self.loop = asyncio.get_event_loop()
            self.audio_queue = asyncio.Queue(maxsize=100)  # Buffer up to 10 seconds at 100ms chunks

            # Create audio streamer
            self.audio_streamer = PipeBasedAudioStreamer(
                loop=self.loop,
                queue=self.audio_queue,
                chunk_duration_ms=32,  # 32ms chunks for VAD compatibility (512 samples at 16kHz)
                sample_rate=self.args.sample_rate,
                audio_device=self.args.device
            )

            # Start recording
            if not self.audio_streamer.start_recording():
                raise RuntimeError("Failed to start audio recording")

            self.logger.info("Audio streaming started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start audio streaming: {e}")
            raise

    async def _conversation_loop(self):
        """Main conversation processing loop."""
        self.is_listening = True
        speech_start = None

        while not self.stop_event.is_set():
            try:
                # Get audio chunk with timeout
                if self.audio_queue is None:
                    break
                audio_chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)

                # Get speech probability from Silero VAD
                if self.vad is None:
                    break
                speech_prob = self.vad.process_chunk(audio_chunk)

                # Advanced VAD with hysteresis and state machine
                if speech_prob > self.vad_threshold:
                    self.consecutive_speech += 1
                    self.consecutive_silence = 0

                    if self.vad_state == "silence" and self.consecutive_speech >= 2:
                        # Require 2 consecutive speech chunks to start
                        self.vad_state = "speech"
                        if speech_start is None:
                            speech_start = time.time() - (0.1 * self.consecutive_speech)  # Backdate start
                            self.current_utterance = []
                            self.logger.debug(f"Speech started (prob: {speech_prob:.3f})")

                    # Add to utterance if in speech state
                    if self.vad_state == "speech" and speech_start is not None:
                        self.current_utterance.append(audio_chunk)
                elif speech_prob < (self.vad_threshold - 0.15):  # Hysteresis
                    self.consecutive_silence += 1
                    self.consecutive_speech = 0

                    if self.vad_state == "speech":
                        # We're in speech, add to utterance even during brief silence
                        if speech_start is not None:
                            self.current_utterance.append(audio_chunk)

                        # Check if silence is long enough to end utterance
                        required_silence = int(self.max_silence_duration * self.chunks_per_second)
                        if self.consecutive_silence >= required_silence:
                            # Calculate speech duration
                            if speech_start is not None:
                                speech_duration = time.time() - speech_start

                                if speech_duration >= self.min_speech_duration:
                                    # Valid utterance, process it
                                    self.vad_state = "silence"
                                    await self._process_utterance()
                                    speech_start = None
                                    self.consecutive_speech = 0
                                    self.consecutive_silence = 0
                                else:
                                    # Too short, reset
                                    self.logger.debug(f"Speech too short ({speech_duration:.2f}s), ignoring")
                                    self.vad_state = "silence"
                                    speech_start = None
                                    self.current_utterance = []
                else:
                    # In the hysteresis zone, maintain current state
                    if self.vad_state == "speech" and speech_start is not None:
                        self.current_utterance.append(audio_chunk)

            except asyncio.TimeoutError:
                # No audio data - continue loop
                continue
            except Exception as e:
                self.logger.error(f"Error in conversation loop: {e}")
                break

    async def _process_utterance(self) -> None:
        """Process the current utterance in a separate thread."""
        if not self.current_utterance or self.is_processing:
            return

        self.is_processing = True
        utterance_data = np.concatenate(self.current_utterance)

        try:
            await self._send_status("processing", "Transcribing speech...")

            # Process in executor to avoid blocking the listening loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._transcribe_audio, utterance_data)

            if result["success"]:
                await self._send_transcription(result)
            else:
                await self._send_error(f"Transcription failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.logger.exception(f"Error processing utterance: {e}")
            await self._send_error(f"Processing error: {e}")
        finally:
            self.is_processing = False
            await self._send_status("listening", "Ready for next utterance")

    def _transcribe_audio(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Transcribe audio data using Whisper."""
        try:
            import tempfile
            import wave

            # Save audio to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                with wave.open(tmp_file.name, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(self.args.sample_rate)
                    wav_file.writeframes(audio_data.astype(np.int16).tobytes())

                # Transcribe
                if self.model is None:
                    raise RuntimeError("Model not loaded")
                segments, info = self.model.transcribe(tmp_file.name, language=self.args.language)
                text = "".join([segment.text for segment in segments]).strip()

                self.logger.info(f"Transcribed: '{text}' ({len(text)} chars)")

            # Log VAD stats
            if self.vad:
                vad_stats = self.vad.get_stats()
                self.logger.debug(f"VAD stats: {vad_stats}")

            return {
                "success": True,
                "text": text,
                "language": info.language if hasattr(info, 'language') else 'en',
                "duration": len(audio_data) / self.args.sample_rate,
                "confidence": 0.95  # Placeholder - Whisper doesn't provide confidence
            }

        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "duration": 0
            }

    async def _send_status(self, status: str, message: str):
        """Send status message."""
        result = {
            "type": "status",
            "mode": "conversation",
            "status": status,
            "message": message,
            "timestamp": time.time()
        }

        if self.args.format == "json":
            print(json.dumps(result))
        else:
            print(f"[{status.upper()}] {message}", file=sys.stderr)

    async def _send_transcription(self, result: Dict[str, Any]):
        """Send transcription result."""
        output = {
            "type": "transcription",
            "mode": "conversation",
            "text": result["text"],
            "language": result["language"],
            "duration": result["duration"],
            "confidence": result["confidence"],
            "timestamp": time.time()
        }

        if self.args.format == "json":
            print(json.dumps(output))
        else:
            print(result["text"])

    async def _send_error(self, error_message: str):
        """Send error message."""
        result = {
            "type": "error",
            "mode": "conversation",
            "error": error_message,
            "timestamp": time.time()
        }

        if self.args.format == "json":
            print(json.dumps(result))
        else:
            print(f"Error: {error_message}", file=sys.stderr)

    async def _cleanup(self):
        """Clean up resources."""
        self.stop_event.set()

        if self.audio_streamer:
            self.audio_streamer.stop_recording()

        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)

        self.logger.info("Conversation mode cleanup completed")
