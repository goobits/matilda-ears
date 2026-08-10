#!/usr/bin/env python3
"""Conversation Mode - Continuous VAD-based listening for hands-free operation

This mode enables continuous, hands-free listening with:
- Voice Activity Detection (VAD) to detect speech
- Automatic transcription of each utterance
- Immediate return to listening state after transcription
- Interruption support for new speech while processing
"""

import asyncio

from matilda_ears.core.mode_config import ConversationConfig
from matilda_ears.core.vad_state import VADStateMachine, VADEvent

from .base_mode import AudioCaptureEndedError, BaseMode


class ConversationMode(BaseMode):
    """Continuous conversation mode with VAD-based utterance detection."""

    def __init__(self, mode_config: ConversationConfig):
        super().__init__(mode_config)

        # Load VAD parameters from config
        mode_config = self._get_mode_config()

        # Initialize VAD Processor
        self.vad_processor = VADStateMachine(
            sample_rate=self.mode_config.sample_rate,
            threshold=mode_config.get("vad_threshold", 0.5),
            hysteresis=mode_config.get("hysteresis", 0.15),
            min_speech_duration_s=mode_config.get("min_speech_duration_s", 0.5),
            max_silence_duration_s=mode_config.get("max_silence_duration_s", 1.0),
            max_speech_duration_s=mode_config.get("max_speech_duration_s", 30.0),
        )

        self.is_processing = False

        self.logger.info(
            f"VAD config: threshold={self.vad_processor.threshold}, "
            f"min_speech={self.vad_processor.min_speech_duration_s}s, "
            f"max_silence={self.vad_processor.max_silence_duration_s}s"
        )

    async def run(self):
        """Main conversation mode loop."""
        try:
            # Initialize Whisper model
            await self._load_model()

            # Initialize VAD
            await self._initialize_vad()

            await self._start_audio_capture(maxsize=100)

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
        """Initialize VAD Processor."""
        try:
            await asyncio.to_thread(self.vad_processor.initialize)
        except Exception as e:
            self.logger.error(f"Failed to initialize VAD: {e}")
            raise

    async def _conversation_loop(self):
        """Main conversation processing loop."""
        self.vad_processor.reset()

        while not self._stop_requested:
            try:
                audio_chunk = await self._read_audio_chunk()

                # Process with VAD
                event, speech_prob = self.vad_processor.process(audio_chunk)

                if event == VADEvent.START:
                    self.logger.debug(f"Speech started (prob: {speech_prob:.3f})")

                elif event == VADEvent.END:
                    self.logger.debug("Speech ended, processing utterance")
                    await self._process_utterance()
                    self.vad_processor.reset()

            except TimeoutError:
                # No audio data - continue loop
                continue
            except AudioCaptureEndedError as exc:
                self.logger.warning(str(exc))
                break
            except Exception as e:
                self.logger.error(f"Error in conversation loop: {e}")
                break

    async def _process_utterance(self) -> None:
        """Process the current utterance in a separate thread."""
        utterance_data = self.vad_processor.get_audio()

        if len(utterance_data) == 0 or self.is_processing:
            return

        self.is_processing = True

        try:
            await self._send_status("processing", "Transcribing speech...")
            await self._transcribe_and_send(utterance_data)

        except Exception as e:
            self.logger.exception(f"Error processing utterance: {e}")
            await self._send_error(f"Processing error: {e}")
        finally:
            self.is_processing = False
            await self._send_status("listening", "Ready for next utterance")
