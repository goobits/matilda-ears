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
from typing import Dict, Any
from pathlib import Path
import sys

# Add project root to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.absolute()))

from .base_mode import BaseMode

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


class ConversationMode(BaseMode):
    """Continuous conversation mode with VAD-based utterance detection."""

    def __init__(self, args):
        super().__init__(args)
        
        # Load VAD parameters from config
        mode_config = self._get_mode_config()
        
        # VAD and transcription
        self.is_listening = False
        self.is_processing = False
        self.current_utterance = []
        self.vad = None  # Silero VAD instance
        self.vad_threshold = mode_config.get("vad_threshold", 0.5)
        self.min_speech_duration = mode_config.get("min_speech_duration_s", 0.5)
        self.max_silence_duration = mode_config.get("max_silence_duration_s", 1.0)
        self.speech_pad_duration = mode_config.get("speech_pad_duration_s", 0.3)

        # VAD state machine
        self.vad_state = "silence"  # silence, speech, trailing
        self.consecutive_speech = 0
        self.consecutive_silence = 0
        self.chunks_per_second = 10  # 100ms chunks

        # Threading
        self.processing_thread = None
        self.stop_event = threading.Event()
        
        self.logger.info(f"VAD config: threshold={self.vad_threshold}, "
                        f"min_speech={self.min_speech_duration}s, "
                        f"max_silence={self.max_silence_duration}s")

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
            await self._setup_audio_streamer(maxsize=100)  # Buffer up to 10 seconds at 100ms chunks

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
            result = await loop.run_in_executor(None, self._transcribe_audio_with_vad_stats, utterance_data)

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

    def _transcribe_audio_with_vad_stats(self, audio_data: np.ndarray) -> Dict[str, Any]:
        """Transcribe audio data using Whisper and include VAD stats."""
        result = super()._transcribe_audio(audio_data)
        
        # Log VAD stats if available
        if result["success"] and self.vad:
            vad_stats = self.vad.get_stats()
            self.logger.debug(f"VAD stats: {vad_stats}")
        
        return result




    async def _cleanup(self):
        """Clean up resources."""
        self.stop_event.set()

        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)

        await super()._cleanup()
