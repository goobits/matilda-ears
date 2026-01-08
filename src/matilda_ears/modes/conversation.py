#!/usr/bin/env python3
"""Conversation Mode - Continuous VAD-based listening for hands-free operation

This mode enables continuous, hands-free listening with:
- Voice Activity Detection (VAD) to detect speech
- Automatic transcription of each utterance
- Immediate return to listening state after transcription
- Interruption support for new speech while processing
"""

import asyncio
import threading
from typing import Any

from ._imports import np
from .base_mode import BaseMode
from matilda_ears.core.vad import VADProcessor, VADEvent


class ConversationMode(BaseMode):
    """Continuous conversation mode with VAD-based utterance detection."""

    def __init__(self, args):
        super().__init__(args)

        # Load VAD parameters from config
        mode_config = self._get_mode_config()

        # Initialize VAD Processor
        self.vad_processor = VADProcessor(
            sample_rate=self.args.sample_rate,
            threshold=mode_config.get("vad_threshold", 0.5),
            min_speech_duration_s=mode_config.get("min_speech_duration_s", 0.5),
            max_silence_duration_s=mode_config.get("max_silence_duration_s", 1.0),
        )

        # Threading
        self.processing_thread = None
        self.stop_event = threading.Event()
        self.is_processing = False

        self.logger.info(f"VAD config: threshold={self.vad_processor.threshold}, "
                        f"min_speech={self.vad_processor.min_speech_duration_s}s, "
                        f"max_silence={self.vad_processor.max_silence_duration_s}s")

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
        """Initialize VAD Processor."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.vad_processor.initialize)
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
        
        self.vad_processor.reset()

        while not self.stop_event.is_set():
            try:
                # Get audio chunk with timeout
                if self.audio_queue is None:
                    break
                audio_chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)

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

    def _transcribe_audio_with_vad_stats(self, audio_data: np.ndarray) -> dict[str, Any]:
        """Transcribe audio data using Whisper."""
        # We don't have separate VAD stats object from VADProcessor yet, but we could add it
        result = super()._transcribe_audio(audio_data)
        return result

    async def _cleanup(self):
        """Clean up resources."""
        self.stop_event.set()

        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)

        await super()._cleanup()
