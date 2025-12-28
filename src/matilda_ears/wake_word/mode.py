#!/usr/bin/env python3
"""Wake word detection mode for Matilda Ears.

Provides always-listening wake word detection that activates
transcription when "Hey Matilda" (or other wake phrase) is detected.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from ..modes.base_mode import BaseMode
from .detector import WakeWordDetector

logger = logging.getLogger(__name__)


class WakeWordMode(BaseMode):
    """Always-listening wake word detection with automatic agent routing.

    Flow:
    1. Continuously listen for wake word ("Hey Matilda")
    2. When detected, capture full utterance using VAD
    3. Transcribe and return with pre-identified agent

    Reuses:
    - BaseMode: Audio setup, transcription, output methods
    - SileroVAD: Utterance boundary detection (from audio.vad)
    - PipeBasedAudioStreamer: Audio capture (from audio.capture)
    """

    def __init__(self, args):
        """Initialize wake word mode.

        Args:
            args: Namespace with CLI arguments including:
                - agents: Comma-separated agent names (default: "Matilda")
                - threshold: Detection threshold (default: 0.5)
                - sample_rate: Audio sample rate (default: 16000)
        """
        super().__init__(args)

        # Wake word specific config
        mode_config = self._get_mode_config()
        self.agents = self._parse_agents(getattr(args, "agents", None), mode_config)
        self.threshold = getattr(args, "threshold", None) or mode_config.get("threshold", 0.5)
        self.silence_duration = mode_config.get("silence_duration", 0.8)
        self.noise_suppression = mode_config.get("noise_suppression", True)

        # Components (initialized in run)
        self.detector: Optional[WakeWordDetector] = None
        self.vad = None
        self._running = False

    def _parse_agents(self, agents_arg: Optional[str], mode_config: Dict) -> List[str]:
        """Parse agents from CLI arg or config."""
        if agents_arg:
            return [a.strip() for a in agents_arg.split(",")]
        return mode_config.get("agents", ["Matilda"])

    async def run(self):
        """Main wake word detection loop."""
        try:
            await self._send_status("initializing", "Loading wake word models...")

            # Load models in executor (CPU-bound)
            loop = asyncio.get_event_loop()
            self.detector = await loop.run_in_executor(
                None,
                lambda: WakeWordDetector(
                    agents=self.agents,
                    threshold=self.threshold,
                    noise_suppression=self.noise_suppression,
                )
            )

            # Load VAD for utterance boundary detection
            await self._initialize_vad()

            # Load transcription backend
            await self._load_model()

            # Setup audio streaming
            await self._setup_audio_streamer(
                maxsize=2000,
                chunk_duration_ms=WakeWordDetector.CHUNK_DURATION_MS
            )

            # Start audio capture
            self.audio_streamer.start_recording()
            self.is_recording = True

            await self._send_status(
                "listening",
                f"Listening for: {', '.join(self.detector.loaded_agents)}",
                {"agents": self.detector.loaded_agents}
            )

            # Main detection loop
            self._running = True
            while self._running:
                result = await self._detection_loop()
                if result:
                    # Send transcription with agent info
                    await self._send_transcription(result, {"agent": result.get("agent")})

                    # Reset for next detection
                    self.detector.reset()
                    await self._send_status(
                        "listening",
                        f"Ready for next wake word",
                        {"agents": self.detector.loaded_agents}
                    )

        except KeyboardInterrupt:
            await self._send_status("interrupted", "Wake word mode stopped")
        except Exception as e:
            self.logger.exception(f"Wake word mode error: {e}")
            await self._send_error(f"Wake word mode failed: {e}")
        finally:
            await self._cleanup()

    async def _initialize_vad(self):
        """Initialize VAD for utterance boundary detection."""
        try:
            from ..audio.vad import SileroVAD

            loop = asyncio.get_event_loop()
            mode_config = self._get_mode_config()

            self.vad = await loop.run_in_executor(
                None,
                lambda: SileroVAD(
                    sample_rate=self.args.sample_rate,
                    threshold=mode_config.get("vad_threshold", 0.5),
                    min_speech_duration=mode_config.get("min_speech_duration", 0.25),
                    min_silence_duration=self.silence_duration,
                    use_onnx=True
                )
            )
            self.logger.info("VAD initialized for utterance detection")
        except ImportError as e:
            self.logger.warning(f"VAD not available, using simple silence detection: {e}")
            self.vad = None

    async def _detection_loop(self) -> Optional[Dict[str, Any]]:
        """Listen for wake word and capture utterance.

        Returns:
            Transcription result dict with agent, or None if stopped.
        """
        audio_buffer = []

        while self._running:
            try:
                # Get audio chunk (80ms for OpenWakeWord)
                chunk = await asyncio.wait_for(
                    self.audio_queue.get(),
                    timeout=0.1
                )

                # Normalize to float32 for OpenWakeWord
                if chunk.dtype == np.int16:
                    chunk_float = chunk.astype(np.float32) / 32768.0
                else:
                    chunk_float = chunk

                # Check for wake word
                agent = self.detector.detect(chunk_float)

                if agent:
                    self.logger.info(f"Wake word detected: {agent}")
                    await self._send_status(
                        "wake_word_detected",
                        f"Detected: Hey {agent}",
                        {"agent": agent}
                    )

                    # Capture full utterance
                    utterance_chunks = await self._capture_utterance()

                    if utterance_chunks:
                        # Transcribe
                        audio_array = np.concatenate(utterance_chunks)
                        result = await asyncio.get_event_loop().run_in_executor(
                            None,
                            self._transcribe_audio,
                            audio_array
                        )

                        if result.get("success"):
                            result["agent"] = agent
                            result["wake_word_detected"] = True
                            return result
                        else:
                            await self._send_error(f"Transcription failed: {result.get('error')}")
                    else:
                        await self._send_status("timeout", "No speech detected after wake word")

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Detection loop error: {e}")
                await asyncio.sleep(0.1)

        return None

    async def _capture_utterance(self) -> List["np.ndarray"]:
        """Capture audio until silence detected by VAD.

        Returns:
            List of audio chunks forming the utterance.
        """
        chunks = []
        silence_count = 0
        max_silence_chunks = int(self.silence_duration * 1000 / WakeWordDetector.CHUNK_DURATION_MS)
        max_duration_chunks = int(30.0 * 1000 / WakeWordDetector.CHUNK_DURATION_MS)  # 30s max

        self.logger.debug(f"Capturing utterance (max silence: {max_silence_chunks} chunks)")

        while len(chunks) < max_duration_chunks:
            try:
                chunk = await asyncio.wait_for(
                    self.audio_queue.get(),
                    timeout=0.5
                )
                chunks.append(chunk)

                # Check VAD for speech/silence
                if self.vad is not None:
                    prob = self.vad.process_chunk(chunk)
                    if prob < self.vad.threshold:
                        silence_count += 1
                    else:
                        silence_count = 0
                else:
                    # Simple amplitude-based silence detection
                    amplitude = np.abs(chunk).mean()
                    if amplitude < 500:  # Threshold for 16-bit audio
                        silence_count += 1
                    else:
                        silence_count = 0

                if silence_count >= max_silence_chunks:
                    self.logger.debug(f"Silence detected, captured {len(chunks)} chunks")
                    break

            except asyncio.TimeoutError:
                self.logger.warning("Timeout waiting for audio during utterance capture")
                break

        return chunks

    def stop(self):
        """Stop the detection loop."""
        self._running = False

    async def _cleanup(self):
        """Clean up resources."""
        self._running = False
        await super()._cleanup()
