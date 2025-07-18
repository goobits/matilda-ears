#!/usr/bin/env python3
"""
Listen-Once Mode - Single utterance capture with VAD

This mode provides automatic speech detection and transcription of a single utterance:
- Uses Voice Activity Detection (VAD) to detect speech
- Captures one complete utterance
- Exits after transcription
- Perfect for command-line pipelines and single voice commands
"""

import asyncio
import time
import json
from typing import Dict, Any
from pathlib import Path
import sys
import tempfile
import wave

# Add project root to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.absolute()))

from src.core.config import get_config, setup_logging
from src.audio.capture import PipeBasedAudioStreamer
from src.audio.vad import SileroVAD

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


class ListenOnceMode:
    """Single utterance capture mode with VAD-based detection."""

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

        # VAD and utterance detection
        self.vad = None
        self.vad_threshold = 0.5
        self.min_speech_duration = 0.3  # Shorter minimum for commands
        self.max_silence_duration = 0.8  # Shorter silence for responsiveness
        self.max_recording_duration = 30.0  # Maximum recording time

        # VAD state
        self.vad_state = "waiting"  # waiting, speech, trailing_silence
        self.consecutive_speech = 0
        self.consecutive_silence = 0
        self.chunks_per_second = 10  # 100ms chunks

        # Recording state
        self.utterance_chunks = []
        self.speech_started = False
        self.recording_start_time = None

        # Whisper model
        self.model = None

        # Check dependencies
        if not NUMPY_AVAILABLE:
            raise ImportError(
                "NumPy is required for listen-once mode. "
                "Install with: pip install numpy"
            )

        self.logger.info("Listen-once mode initialized")

    async def run(self):
        """Main listen-once mode execution."""
        try:
            # Send initial status for JSON mode
            if self.args.format == "json":
                await self._send_status("initializing", "Loading models...")

            # Initialize Whisper model
            await self._load_model()

            # Initialize VAD
            await self._initialize_vad()

            # Start audio streaming
            await self._start_audio_streaming()

            # Send listening status
            await self._send_status("listening", "Listening for speech...")

            # Capture single utterance
            utterance_captured = await self._capture_utterance()

            if utterance_captured:
                # Process and transcribe
                await self._process_utterance()
            else:
                await self._send_error("No speech detected within timeout period")

        except KeyboardInterrupt:
            await self._send_status("interrupted", "Listen-once mode stopped by user")
        except Exception as e:
            self.logger.exception(f"Listen-once mode error: {e}")
            await self._send_error(f"Listen-once mode failed: {e}")
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
        """Initialize Silero VAD."""
        try:
            self.logger.info("Initializing Silero VAD...")

            loop = asyncio.get_event_loop()
            self.vad = await loop.run_in_executor(
                None,
                lambda: SileroVAD(
                    sample_rate=self.args.sample_rate,
                    threshold=self.vad_threshold,
                    min_speech_duration=self.min_speech_duration,
                    min_silence_duration=self.max_silence_duration,
                    use_onnx=True
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
        """Initialize and start audio streaming."""
        try:
            self.loop = asyncio.get_event_loop()
            self.audio_queue = asyncio.Queue(maxsize=100)

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

            self.recording_start_time = time.time()
            self.logger.info("Audio streaming started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start audio streaming: {e}")
            raise

    async def _capture_utterance(self):
        """Capture a single utterance using VAD."""
        utterance_complete = False

        while not utterance_complete:
            try:
                # Check for timeout
                if self.recording_start_time is not None and time.time() - self.recording_start_time > self.max_recording_duration:
                    self.logger.warning("Maximum recording duration reached")
                    break

                # Get audio chunk with timeout
                if self.audio_queue is None:
                    break
                audio_chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)

                # Process with VAD
                if self.vad is None:
                    break
                speech_prob = self.vad.process_chunk(audio_chunk)

                # Update VAD state machine
                if self.vad_state == "waiting":
                    if speech_prob > self.vad_threshold:
                        self.consecutive_speech += 1
                        if self.consecutive_speech >= 2:  # Require 2 chunks to start
                            self.vad_state = "speech"
                            self.speech_started = True
                            self.utterance_chunks = []  # Clear any noise
                            self.logger.debug(f"Speech detected (prob: {speech_prob:.3f})")
                            await self._send_status("recording", "Speech detected, recording...")
                    else:
                        self.consecutive_speech = 0

                elif self.vad_state == "speech":
                    # Always add chunks during speech state
                    self.utterance_chunks.append(audio_chunk)

                    if speech_prob < (self.vad_threshold - 0.15):  # Hysteresis
                        self.consecutive_silence += 1
                        self.consecutive_speech = 0

                        # Check if silence is long enough to end
                        required_silence = int(self.max_silence_duration * self.chunks_per_second)
                        if self.consecutive_silence >= required_silence:
                            # Check minimum speech duration
                            speech_duration = len(self.utterance_chunks) / self.chunks_per_second
                            if speech_duration >= self.min_speech_duration:
                                self.logger.debug(f"Speech ended after {speech_duration:.2f}s")
                                utterance_complete = True
                            else:
                                # Too short, reset
                                self.logger.debug(f"Speech too short ({speech_duration:.2f}s)")
                                self.vad_state = "waiting"
                                self.utterance_chunks = []
                                self.consecutive_silence = 0
                    else:
                        self.consecutive_silence = 0
                        self.consecutive_speech += 1

            except asyncio.TimeoutError:
                # No audio data - continue waiting
                continue
            except Exception as e:
                self.logger.error(f"Error capturing utterance: {e}")
                break

        return len(self.utterance_chunks) > 0

    async def _process_utterance(self):
        """Process and transcribe the captured utterance."""
        if not self.utterance_chunks:
            await self._send_error("No audio data to transcribe")
            return

        try:
            await self._send_status("processing", "Processing speech...")

            # Combine audio chunks
            audio_array = np.concatenate(self.utterance_chunks)
            duration = len(audio_array) / self.args.sample_rate

            self.logger.info(f"Transcribing {duration:.2f}s of audio")

            # Transcribe in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._transcribe_audio, audio_array)

            if result["success"]:
                await self._send_transcription(result)
            else:
                await self._send_error(f"Transcription failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            self.logger.exception(f"Error processing utterance: {e}")
            await self._send_error(f"Processing error: {e}")

    def _transcribe_audio(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Transcribe audio data using Whisper."""
        try:
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
                    "confidence": 0.95  # Placeholder
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
        if self.args.format == "json":
            result = {
                "type": "status",
                "mode": "listen_once",
                "status": status,
                "message": message,
                "timestamp": time.time()
            }
            print(json.dumps(result))
        elif status == "listening":
            # Only show listening message in text mode
            print(message, file=sys.stderr)

    async def _send_transcription(self, result: Dict[str, Any]):
        """Send transcription result."""
        if self.args.format == "json":
            output = {
                "type": "transcription",
                "mode": "listen_once",
                "text": result["text"],
                "language": result["language"],
                "duration": result["duration"],
                "confidence": result["confidence"],
                "model": self.args.model,
                "timestamp": time.time()
            }
            print(json.dumps(output))
        else:
            # Text mode - just print the transcribed text
            print(result["text"])

    async def _send_error(self, error_message: str):
        """Send error message."""
        if self.args.format == "json":
            result = {
                "type": "error",
                "mode": "listen_once",
                "error": error_message,
                "timestamp": time.time()
            }
            print(json.dumps(result))
        else:
            print(f"Error: {error_message}", file=sys.stderr)

    async def _cleanup(self):
        """Clean up resources."""
        if self.audio_streamer:
            self.audio_streamer.stop_recording()

        self.logger.info("Listen-once mode cleanup completed")
