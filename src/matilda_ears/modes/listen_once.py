#!/usr/bin/env python3
"""Listen-Once Mode - Single utterance capture with VAD

This mode provides automatic speech detection and transcription of a single utterance:
- Uses Voice Activity Detection (VAD) to detect speech
- Captures one complete utterance
- Exits after transcription
- Perfect for command-line pipelines and single voice commands
"""

import asyncio
import sys
import time

import numpy as np

from matilda_ears.core.mode_config import ListenOnceConfig
from matilda_ears.core.vad_state import VADStateMachine, VADEvent

from .base_mode import AudioCaptureEndedError, BaseMode


class ListenOnceMode(BaseMode):
    """Single utterance capture mode with VAD-based detection."""

    def __init__(self, mode_config: ListenOnceConfig):
        super().__init__(mode_config)

        # Load VAD parameters from config
        mode_config = self._get_mode_config()

        # Initialize VAD Processor
        self.vad_processor = VADStateMachine(
            sample_rate=self.mode_config.sample_rate,
            threshold=mode_config.get("vad_threshold", 0.5),
            hysteresis=mode_config.get("hysteresis", 0.15),
            min_speech_duration_s=mode_config.get("min_speech_duration_s", 0.3),
            max_silence_duration_s=mode_config.get("max_silence_duration_s", 0.8),
            max_speech_duration_s=mode_config.get("max_speech_duration_s", 30.0),
        )

        self.max_recording_duration = mode_config.get("max_recording_duration_s", 30.0)
        self.recording_start_time = None
        self.speech_started = False

        self.logger.info(
            f"VAD config: threshold={self.vad_processor.threshold}, "
            f"min_speech={self.vad_processor.min_speech_duration_s}s, "
            f"max_silence={self.vad_processor.max_silence_duration_s}s, "
            f"max_recording={self.max_recording_duration}s"
        )

    async def run(self):
        """Main listen-once mode execution."""
        try:
            # Send initial status for JSON mode
            if self.mode_config.format == "json":
                await self._send_status("initializing", "Loading models...")

            # Initialize Whisper model
            await self._load_model()

            # Initialize VAD
            await self._initialize_vad()

            await self._start_audio_capture(maxsize=100)
            self.recording_start_time = time.monotonic()

            # Send listening status
            await self._send_status("listening", "Listening for speech...")

            # Capture single utterance
            utterance_audio = await self._capture_utterance()
            await self._stop_audio_capture()

            if utterance_audio is not None and len(utterance_audio) > 0:
                # Process and transcribe
                await self._process_utterance(utterance_audio)
            # In piped mode, don't send error to avoid breaking the pipeline
            # Just exit quietly if no speech detected
            elif not sys.stdout.isatty():
                # Piped mode - exit silently
                pass
            else:
                # Interactive mode - show error
                await self._send_error("No speech detected within timeout period")

        except KeyboardInterrupt:
            await self._send_status("interrupted", "Listen-once mode stopped by user")
        except Exception as e:
            self.logger.exception(f"Listen-once mode error: {e}")
            await self._send_error(f"Listen-once mode failed: {e}")
        finally:
            await self._cleanup()

    async def _initialize_vad(self):
        """Initialize VAD Processor."""
        try:
            await asyncio.to_thread(self.vad_processor.initialize)
        except Exception as e:
            self.logger.error(f"Failed to initialize VAD: {e}")
            raise

    async def _capture_utterance(self):
        """Capture a single utterance using VAD."""
        utterance_complete = False

        self.vad_processor.reset()
        self.speech_started = False

        while not utterance_complete and not self._stop_requested:
            try:
                # Check for timeout
                if (
                    self.recording_start_time is not None
                    and time.monotonic() - self.recording_start_time > self.max_recording_duration
                ):
                    self.logger.warning("Maximum recording duration reached")
                    break

                # Get audio chunk with timeout
                audio_chunk = await self._read_audio_chunk()

                # Process with VAD
                event, speech_prob = self.vad_processor.process(audio_chunk)

                if event == VADEvent.START:
                    self.speech_started = True
                    self.logger.debug(f"Speech detected (prob: {speech_prob:.3f})")
                    await self._send_status("recording", "Speech detected, recording...")

                elif event == VADEvent.END:
                    self.logger.debug("Speech ended")
                    utterance_complete = True

            except TimeoutError:
                # No audio data - continue waiting
                continue
            except AudioCaptureEndedError as exc:
                self.logger.warning(str(exc))
                break
            except Exception as e:
                self.logger.error(f"Error capturing utterance: {e}")
                break

        if self.speech_started and utterance_complete:
            return self.vad_processor.get_audio()
        return None

    async def _process_utterance(self, audio_data: np.ndarray) -> None:
        """Process and transcribe the captured utterance."""
        if audio_data is None or len(audio_data) == 0:
            await self._send_error("No audio data to transcribe")
            return

        await self._send_status("processing", "Processing speech...")
        try:
            await self._transcribe_and_send(audio_data)
        except Exception as e:
            self.logger.exception(f"Error processing utterance: {e}")
            await self._send_error(f"Processing error: {e}")
