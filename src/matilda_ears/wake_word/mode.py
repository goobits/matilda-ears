#!/usr/bin/env python3
"""Wake word detection mode for Matilda Ears.

Provides always-listening wake word detection that activates
transcription when "Hey Matilda" (or other wake phrase) is detected.
Supports multiple aliases per agent (e.g., "Hey Matilda", "computer", "assistant").
"""

import asyncio
import logging
from typing import Any

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from ..core.mode_config import WakeWordConfig
from ..modes.base_mode import AudioCaptureEndedError, BaseMode
from .detector import WakeWordDetector

logger = logging.getLogger(__name__)


class WakeWordMode(BaseMode):
    """Always-listening wake word detection with automatic agent routing.

    Flow:
    1. Continuously listen for wake word ("Hey Matilda", "computer", etc.)
    2. When detected, capture full utterance using VAD
    3. Transcribe and return with pre-identified agent

    Supports multiple wake word aliases per agent:
    - CLI: --agent-aliases="Matilda:hey_matilda,computer;Bob:hey_bob"
    - Config: agent_aliases: [{agent: "Matilda", aliases: ["hey_matilda", "computer"]}]

    Reuses:
    - BaseMode: Audio setup, transcription, output methods
    - SileroVAD: Utterance boundary detection (from audio.vad)
    - PipeBasedAudioStreamer: Audio capture (from audio.capture)
    """

    def __init__(self, mode_config: WakeWordConfig):
        """Initialize wake word mode."""
        super().__init__(mode_config)

        # Wake word specific config
        settings = self._get_mode_config()

        self.agent_aliases = self._parse_agent_aliases(mode_config.agent_aliases, settings)

        # Threshold from CLI or config (explicit None checks to allow threshold=0.0)
        if mode_config.threshold is not None:
            self.threshold = mode_config.threshold
        else:
            self.threshold = settings.get("threshold", 0.5)
        self.silence_duration = settings.get("silence_duration", 0.8)
        self.vad_hysteresis = settings.get("hysteresis", 0.2)
        self.max_speech_duration_s = settings.get("max_speech_duration_s", 10.0)
        self.noise_suppression = settings.get("noise_suppression", True)

        # Backend selection (CLI takes precedence over config)
        self.wake_word_backend = mode_config.backend or settings.get("backend", "openwakeword")
        self.access_key = mode_config.access_key or settings.get("access_key")

        # Components (initialized in run)
        self.detector: WakeWordDetector | None = None
        self.vad = None

    def _parse_agent_aliases(self, cli_aliases: str | None, mode_config: dict) -> dict[str, list[str]] | None:
        """Parse agent aliases from CLI or config.

        Priority:
        1. CLI --agent-aliases="Matilda:hey_matilda,computer;Bob:hey_bob"
        2. Config agent_aliases: [{agent: "Matilda", aliases: [...]}]

        Returns:
            Dict mapping agent names to list of wake phrases, or None for defaults.

        """
        # CLI --agent-aliases (highest priority)
        if cli_aliases:
            return WakeWordDetector.parse_cli_aliases(cli_aliases)

        # Config agent_aliases
        if "agent_aliases" in mode_config:
            result = {}
            for item in mode_config["agent_aliases"]:
                result[item["agent"]] = item["aliases"]
            return result

        return None

    async def run(self):
        """Main wake word detection loop."""
        try:
            await self._send_status("initializing", "Loading wake word models...")

            # Load models in executor (CPU-bound)
            self.detector = await asyncio.to_thread(
                lambda: WakeWordDetector(
                    agent_aliases=self.agent_aliases,
                    threshold=self.threshold,
                    noise_suppression=self.noise_suppression,
                    backend=self.wake_word_backend,
                    access_key=self.access_key,
                )
            )

            # Load VAD for utterance boundary detection
            await self._initialize_vad()

            # Load transcription backend
            await self._load_model()

            # Setup audio streaming (chunk size depends on backend)
            await self._start_audio_capture(maxsize=2000, chunk_duration_ms=self.detector.CHUNK_DURATION_MS)

            # Build listening message showing agents and their aliases
            aliases_info = self.detector.agent_aliases
            listening_msg = "Listening for: " + ", ".join(
                f"{agent} ({', '.join(phrases)})" for agent, phrases in aliases_info.items()
            )
            await self._send_status(
                "listening", listening_msg, {"agents": self.detector.loaded_agents, "aliases": aliases_info}
            )

            # Main detection loop
            while not self._stop_requested:
                result = await self._detection_loop()
                if result:
                    # Send transcription with agent info
                    await self._send_transcription(result, {"agent": result.get("agent")})

                    # Reset for next detection
                    self.detector.reset()
                    await self._send_status(
                        "listening", "Ready for next wake word", {"agents": self.detector.loaded_agents}
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

            mode_config = self._get_mode_config()

            self.vad = await asyncio.to_thread(
                lambda: SileroVAD(
                    sample_rate=self.mode_config.sample_rate,
                    threshold=mode_config.get("vad_threshold", 0.5),
                    min_speech_duration=mode_config.get("min_speech_duration", 0.25),
                    min_silence_duration=self.silence_duration,
                    use_onnx=True,
                )
            )
            self.logger.info("VAD initialized for utterance detection")
        except ImportError as e:
            self.logger.warning(f"VAD not available, using simple silence detection: {e}")
            self.vad = None

    async def _detection_loop(self) -> dict[str, Any] | None:
        """Listen for wake word and capture utterance.

        Returns:
            Transcription result dict with agent, or None if stopped.

        """
        while not self._stop_requested:
            try:
                chunk = await self._read_audio_chunk()

                # Normalize to float32 for OpenWakeWord
                if chunk.dtype == np.int16:
                    chunk_float = chunk.astype(np.float32) / 32768.0
                else:
                    chunk_float = chunk

                # Check for wake word
                detection = self.detector.detect(chunk_float)

                if detection:
                    agent, wake_phrase, confidence = detection
                    self.logger.info(
                        f"Wake word detected: agent='{agent}', phrase='{wake_phrase}', confidence={confidence:.2%}"
                    )
                    await self._send_status(
                        "wake_word_detected",
                        f"Detected: {wake_phrase} -> {agent}",
                        {"agent": agent, "wake_phrase": wake_phrase, "confidence": confidence},
                    )

                    # Capture full utterance
                    utterance_chunks = await self._capture_utterance()

                    if utterance_chunks:
                        # Transcribe
                        audio_array = np.concatenate(utterance_chunks)
                        result = await self._transcribe_async(audio_array)

                        if result.get("success"):
                            result["agent"] = agent
                            result["wake_phrase"] = wake_phrase
                            result["wake_word_detected"] = True
                            return result
                        await self._send_error(f"Transcription failed: {result.get('error')}")
                    else:
                        await self._send_status("timeout", "No speech detected after wake word")

            except TimeoutError:
                continue
            except AudioCaptureEndedError as exc:
                self.logger.warning(str(exc))
                break
            except Exception as e:
                self.logger.error(f"Detection loop error: {e}")
                await asyncio.sleep(0.1)

        return None

    async def _capture_utterance(self) -> list["np.ndarray"]:
        """Capture audio until silence detected by VAD.

        Returns:
            List of audio chunks forming the utterance.

        """
        chunks = []
        silence_count = 0
        chunk_duration_ms = self.detector.CHUNK_DURATION_MS if self.detector else 80
        max_silence_chunks = int(self.silence_duration * 1000 / chunk_duration_ms)
        max_duration_chunks = int(self.max_speech_duration_s * 1000 / chunk_duration_ms)

        self.logger.debug(f"Capturing utterance (max silence: {max_silence_chunks} chunks)")

        while len(chunks) < max_duration_chunks and not self._stop_requested:
            try:
                chunk = await self._read_audio_chunk(timeout_seconds=0.5)
                chunks.append(chunk)

                # Check VAD for speech/silence
                if self.vad is not None:
                    prob = self.vad.process_chunk(chunk)
                    if prob < (self.vad.threshold - self.vad_hysteresis):
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

            except TimeoutError:
                self.logger.warning("Timeout waiting for audio during utterance capture")
                break
            except AudioCaptureEndedError as exc:
                self.logger.warning(str(exc))
                break

        return chunks

    async def _cleanup(self):
        """Clean up resources."""
        if self.detector:
            self.detector.close()
            self.detector = None
        await super()._cleanup()
