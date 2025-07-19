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
from typing import Dict, Any
from pathlib import Path
import sys

# Add project root to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.absolute()))

from .base_mode import BaseMode
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


class ListenOnceMode(BaseMode):
    """Single utterance capture mode with VAD-based detection."""

    def __init__(self, args):
        super().__init__(args)
        
        # Load VAD parameters from config
        mode_config = self._get_mode_config()
        
        # VAD and utterance detection
        self.vad = None
        self.vad_threshold = mode_config.get("vad_threshold", 0.5)
        self.min_speech_duration = mode_config.get("min_speech_duration_s", 0.3)
        self.max_silence_duration = mode_config.get("max_silence_duration_s", 0.8)
        self.max_recording_duration = mode_config.get("max_recording_duration_s", 30.0)

        # VAD state
        self.vad_state = "waiting"  # waiting, speech, trailing_silence
        self.consecutive_speech = 0
        self.consecutive_silence = 0
        self.chunks_per_second = 10  # 100ms chunks

        # Recording state
        self.utterance_chunks = []
        self.speech_started = False
        self.recording_start_time = None
        
        self.logger.info(f"VAD config: threshold={self.vad_threshold}, "
                        f"min_speech={self.min_speech_duration}s, "
                        f"max_silence={self.max_silence_duration}s, "
                        f"max_recording={self.max_recording_duration}s")

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
            await self._setup_audio_streamer(maxsize=100)

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

        await self._send_status("processing", "Processing speech...")
        # Directly pass the utterance_chunks to the flexible helper
        await self._process_and_transcribe_collected_audio(self.utterance_chunks)

    def _transcribe_audio_with_vad_stats(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Transcribe audio data using Whisper and include VAD stats."""
        result = super()._transcribe_audio(audio_data)
        
        # Log VAD stats if available
        if result["success"] and self.vad:
            vad_stats = self.vad.get_stats()
            self.logger.debug(f"VAD stats: {vad_stats}")
            result["model"] = self.args.model
        
        return result


    async def _send_transcription(self, result: Dict[str, Any]):
        """Send transcription result with model info."""
        extra = {"model": self.args.model} if "model" in result else {}
        await super()._send_transcription(result, extra)


    async def _cleanup(self):
        """Clean up resources."""
        await super()._cleanup()
