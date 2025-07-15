#!/usr/bin/env python3
"""Unified Transcription Client - Consolidates all transcription-related functionality.

This module provides a single interface for all client-side transcription operations,
including WebSocket connections, streaming audio, batch processing, and circuit breaking.
"""

import os
import sys
import asyncio
import websockets
import json
import base64
import time
import threading
import wave
import ssl
import numpy as np
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Any, Tuple, Callable, Dict

# Add project root to path for imports - cross-platform compatible
def ensure_project_root_in_path():
    """Ensure the project root is in sys.path for imports to work."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    while current_dir != os.path.dirname(current_dir):  # Stop at filesystem root
        if os.path.exists(os.path.join(current_dir, "pyproject.toml")) or os.path.exists(
            os.path.join(current_dir, "config.jsonc")
        ):
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            return current_dir
        current_dir = os.path.dirname(current_dir)

    # Fallback: assume we're in src/transcription/ and go up two levels
    fallback_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if fallback_root not in sys.path:
        sys.path.insert(0, fallback_root)
    return fallback_root

ensure_project_root_in_path()

from ..utils.ssl import create_ssl_context  # noqa: E402
from ..core.config import get_config, setup_logging  # noqa: E402
from ..audio.encoder import OpusEncoder  # noqa: E402
from ..audio.opus_batch import OpusBatchEncoder  # noqa: E402

# Get config instance
config = get_config()
logger = setup_logging(__name__, log_filename="transcription.txt")


# ========================= CUSTOM EXCEPTIONS =========================


class TranscriptionError(Exception):
    """Base exception for transcription-related errors."""


class StreamingError(TranscriptionError):
    """Exception for streaming-related errors."""


class TranscriptionConnectionError(TranscriptionError):
    """Exception for connection-related errors."""


# ========================= CIRCUIT BREAKER =========================


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""

    failure_threshold: int = 3  # Failures before opening
    timeout_seconds: int = 30  # How long to stay open
    success_threshold: int = 2  # Successes needed to close from half-open


class CircuitBreaker:
    """Lightweight circuit breaker for WebSocket connections"""

    def __init__(self, config_obj: Optional[CircuitBreakerConfig] = None):
        self.config = config_obj or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0

    def can_execute(self) -> bool:
        """Check if operation should be allowed"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if time.time() - self.last_failure_time >= self.config.timeout_seconds:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return True
            return False

        # HALF_OPEN state - allow limited requests
        return True

    def record_success(self):
        """Record successful operation"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0

        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0  # Reset on success

    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN

        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0

    def execute(self, func: Callable[[], Any]) -> Tuple[bool, Any, Optional[str]]:
        """Execute function with circuit breaker protection

        Returns:
            (success: bool, result: Any, error_message: Optional[str])

        """
        if not self.can_execute():
            return False, None, f"Circuit breaker is {self.state.value}"

        try:
            result = func()
            self.record_success()
            return True, result, None
        except Exception as e:
            self.record_failure()
            return False, None, str(e)

    def get_status(self) -> dict:
        """Get current circuit breaker status for monitoring"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "can_execute": self.can_execute(),
        }


# ========================= STREAMING AUDIO CLIENT =========================


class StreamingAudioClient:
    """WebSocket client for streaming Opus audio to server.

    This class provides a direct interface for streaming audio to the transcription
    server. It is used by StreamHandler and other components that need real-time
    audio streaming capabilities.
    """

    def __init__(
        self, websocket_url: str, auth_token: str, debug_save_audio: bool = False, max_debug_chunks: int = 1000
    ):
        """Initialize streaming client.

        Args:
            websocket_url: WebSocket server URL
            auth_token: Authentication token
            debug_save_audio: If True, save audio chunks for debugging
            max_debug_chunks: Maximum number of debug chunks to keep (default: 1000)

        """
        self.websocket_url = websocket_url
        self.auth_token = auth_token
        self.websocket = None
        self.session_id = None
        self.encoder = OpusEncoder()

        # Debug features with bounded collections
        self.debug_save_audio = debug_save_audio
        self.max_debug_chunks = max_debug_chunks
        self.debug_raw_chunks: list[np.ndarray] = []
        self.debug_opus_chunks: list[bytes] = []
        self.sent_opus_packets = 0
        self.debug_chunk_count = 0

        # Byte counters for debugging
        self.total_raw_bytes = 0
        self.total_opus_bytes = 0

        # Error tracking for streaming
        self._last_streaming_error = None

        logger.info(f"Streaming client initialized for {websocket_url} (debug_audio: {debug_save_audio})")

    def _is_websocket_closed(self) -> bool:
        """Check if WebSocket connection is closed.

        Returns:
            True if WebSocket is closed or invalid

        """
        if not self.websocket:
            return True

        # Check various closed state indicators
        if hasattr(self.websocket, "closed") and self.websocket.closed:
            return True
        if hasattr(self.websocket, "close_code") and self.websocket.close_code is not None:
            return True
        if hasattr(self.websocket, "state") and hasattr(self.websocket.state, "CLOSED"):
            return self.websocket.state == self.websocket.state.CLOSED

        return False

    async def connect(self):
        """Connect to WebSocket server."""
        try:
            # Set up SSL context for self-signed certificates
            ssl_context = None
            if self.websocket_url.startswith("wss://"):
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            self.websocket = await websockets.connect(self.websocket_url, ssl=ssl_context)
            logger.info("Connected to WebSocket server")

            # Wait for welcome message
            if self.websocket is None:
                raise Exception("WebSocket connection failed")
            welcome = await self.websocket.recv()
            welcome_data = json.loads(welcome)
            logger.debug(f"Server welcome: {welcome_data}")

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise

    async def start_stream(self, session_id: Optional[str] = None) -> str:
        """Start audio streaming session.

        Args:
            session_id: Optional session ID (auto-generated if not provided)

        Returns:
            Session ID for this stream

        """
        if not self.websocket:
            raise RuntimeError("Not connected to server")

        # Generate session ID if not provided
        if not session_id:
            import uuid

            session_id = f"stream_{uuid.uuid4().hex[:8]}"

        self.session_id = session_id

        # Send start stream message
        message = {
            "type": "start_stream",
            "token": self.auth_token,
            "session_id": session_id,
            "sample_rate": self.encoder.sample_rate,
            "channels": self.encoder.channels,
        }

        await self.websocket.send(json.dumps(message))

        # Wait for acknowledgment
        response = await self.websocket.recv()
        response_data = json.loads(response)

        if response_data.get("type") == "stream_started":
            logger.info(f"Stream started: {session_id}")
            return session_id
        raise RuntimeError(f"Failed to start stream: {response_data}")

    async def send_audio_chunk(self, audio_data: np.ndarray):
        """Send audio chunk to server.

        Args:
            audio_data: Audio samples to encode and send

        """
        if not self.session_id:
            raise RuntimeError("No active stream session")

        # Check if WebSocket connection is still valid
        if self._is_websocket_closed():
            error_msg = "WebSocket connection is closed - cannot send audio chunk"
            logger.error(error_msg)
            self._last_streaming_error = TranscriptionConnectionError(error_msg)
            return  # Continue buffering but track error

        # Debug: Save raw audio data (bounded collection)
        if self.debug_save_audio and len(audio_data) > 0:
            self.debug_raw_chunks.append(audio_data.copy())
            # Prevent unbounded growth - keep only recent chunks
            if len(self.debug_raw_chunks) > self.max_debug_chunks:
                self.debug_raw_chunks.pop(0)

        # Update raw byte counter
        self.total_raw_bytes += len(audio_data) * 2  # 2 bytes per sample (16-bit audio)

        # Encode chunk (may return None if buffering)
        opus_data = self.encoder.encode_chunk(audio_data)

        if opus_data:
            # Only increment counter when Opus packet is actually created and sent
            self.sent_opus_packets += 1
            self.debug_chunk_count += 1
            self.total_opus_bytes += len(opus_data)

            # Debug: Save Opus data (bounded collection)
            if self.debug_save_audio:
                self.debug_opus_chunks.append(opus_data)
                # Prevent unbounded growth - keep only recent chunks
                if len(self.debug_opus_chunks) > self.max_debug_chunks:
                    self.debug_opus_chunks.pop(0)

            # Send to server
            message = {
                "type": "audio_chunk",
                "session_id": self.session_id,
                "audio_data": base64.b64encode(opus_data).decode("utf-8"),
            }

            try:
                await self.websocket.send(json.dumps(message))
                logger.info(
                    f"📤 SENT opus packet #{self.sent_opus_packets}: {len(audio_data)} samples → {len(opus_data)} bytes"
                )
            except websockets.exceptions.ConnectionClosed as e:
                logger.error(f"Connection closed while sending audio chunk: {e}")
                # Store error for later handling but don't interrupt stream
                self._last_streaming_error = TranscriptionConnectionError(f"Connection lost during streaming: {e}")
            except Exception as e:
                logger.error(f"Failed to send audio chunk: {e}")
                # Store error for later handling but don't interrupt stream
                self._last_streaming_error = StreamingError(f"Failed to send audio chunk: {e}")
        else:
            logger.debug(f"Buffering audio: {len(audio_data)} samples (waiting for complete frame)")

    async def end_stream(self) -> dict:
        """End streaming session and get transcription.

        Returns:
            Transcription result from server

        """
        if not self.session_id:
            raise RuntimeError("No active stream session")

        # Check if we had streaming errors
        if self._last_streaming_error:
            logger.warning(f"Stream had errors during transmission: {self._last_streaming_error}")

        # Check if WebSocket connection is still valid
        if not self.websocket or self._is_websocket_closed():
            logger.error("WebSocket connection is None or closed - cannot end stream properly")
            return {"success": False, "text": "", "message": "WebSocket connection lost"}

        # CRITICAL: Flush any remaining audio from encoder buffer
        logger.info("🔄 FLUSHING encoder buffer")
        final_chunk = self.encoder.flush()
        if final_chunk:
            # Crucially, count this final flushed packet
            self.sent_opus_packets += 1
            self.total_opus_bytes += len(final_chunk)

            # Debug: Save Opus data (bounded collection)
            if self.debug_save_audio:
                self.debug_opus_chunks.append(final_chunk)
                # Prevent unbounded growth - keep only recent chunks
                if len(self.debug_opus_chunks) > self.max_debug_chunks:
                    self.debug_opus_chunks.pop(0)

            # Send the final encoded chunk directly
            message = {
                "type": "audio_chunk",
                "session_id": self.session_id,
                "audio_data": base64.b64encode(final_chunk).decode("utf-8"),
            }
            try:
                await self.websocket.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed as e:
                logger.error(f"Connection closed while sending final chunk: {e}")
                # Save debug audio on connection failure
                if self.debug_save_audio:
                    self.save_debug_audio()
                    # Clear debug collections to free memory
                    self.debug_raw_chunks.clear()
                    self.debug_opus_chunks.clear()
                return {"success": False, "text": "", "message": f"Connection closed during finalization: {e}"}
            except Exception as e:
                logger.error(f"Failed to send final chunk: {e}")
                # Save debug audio on failure
                if self.debug_save_audio:
                    self.save_debug_audio()
                    # Clear debug collections to free memory
                    self.debug_raw_chunks.clear()
                    self.debug_opus_chunks.clear()
                return {"success": False, "text": "", "message": f"Failed to send final chunk: {e}"}
            logger.info(
                f"📤 SENT final flushed opus packet #{self.sent_opus_packets} ({len(final_chunk)} bytes). Final totals: {self.total_raw_bytes} raw, {self.total_opus_bytes} opus"
            )
        else:
            logger.info("🔄 No data to flush from encoder buffer")

        # Send end stream message with correct packet count for verification
        message = {
            "type": "end_stream",
            "session_id": self.session_id,
            "expected_chunks": self.sent_opus_packets,  # Correct count of actual Opus packets sent
            "final_chunk": True,
        }

        try:
            await self.websocket.send(json.dumps(message))
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"Connection closed while sending end stream message: {e}")
            # Save debug audio on connection failure
            if self.debug_save_audio:
                self.save_debug_audio()
                # Clear debug collections to free memory
                self.debug_raw_chunks.clear()
                self.debug_opus_chunks.clear()
            return {"success": False, "text": "", "message": f"Connection closed during stream end: {e}"}
        except Exception as e:
            logger.error(f"Failed to send end stream message: {e}")
            # Save debug audio on failure
            if self.debug_save_audio:
                self.save_debug_audio()
                # Clear debug collections to free memory
                self.debug_raw_chunks.clear()
                self.debug_opus_chunks.clear()
            return {"success": False, "text": "", "message": f"Failed to send end stream message: {e}"}

        # Wait for transcription result
        try:
            response = await self.websocket.recv()
            response_data = json.loads(response)
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"Connection closed while receiving transcription result: {e}")
            # Save debug audio on connection failure
            if self.debug_save_audio:
                self.save_debug_audio()
                # Clear debug collections to free memory
                self.debug_raw_chunks.clear()
                self.debug_opus_chunks.clear()
            return {"success": False, "text": "", "message": f"Connection closed during result reception: {e}"}
        except Exception as e:
            logger.error(f"Failed to receive transcription result: {e}")
            # Save debug audio on failure
            if self.debug_save_audio:
                self.save_debug_audio()
                # Clear debug collections to free memory
                self.debug_raw_chunks.clear()
                self.debug_opus_chunks.clear()
            return {"success": False, "text": "", "message": f"Failed to receive transcription result: {e}"}

        logger.info(f"Stream ended: {self.session_id}")
        self.session_id = None
        self.encoder.reset()
        self.sent_opus_packets = 0

        # Reset byte counters
        self.total_raw_bytes = 0
        self.total_opus_bytes = 0

        # Reset error tracking
        self._last_streaming_error = None

        # Debug: Save audio data for analysis
        if self.debug_save_audio:
            self.save_debug_audio()

        # Clear debug collections after saving to free memory
        self.debug_raw_chunks.clear()
        self.debug_opus_chunks.clear()

        return response_data

    def save_debug_audio(self):
        """Save debug audio data for analysis."""
        import time
        import tempfile

        try:
            timestamp = int(time.time())
            # Use cross-platform temporary directory
            temp_dir = tempfile.gettempdir()
            debug_dir = os.path.join(temp_dir, f"matilda-debug-{timestamp}")
            os.makedirs(debug_dir, exist_ok=True)

            # Save raw audio chunks
            if self.debug_raw_chunks:
                raw_audio = np.concatenate(self.debug_raw_chunks)
                raw_path = os.path.join(debug_dir, "raw_audio.wav")

                with wave.open(raw_path, "wb") as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(16000)  # 16kHz
                    wav_file.writeframes(raw_audio.astype(np.int16).tobytes())

                duration = len(raw_audio) / 16000.0
                logger.info(f"Saved raw audio debug data: {raw_path} ({len(raw_audio)} samples, {duration:.2f}s)")

            # Save Opus chunks
            if self.debug_opus_chunks:
                opus_path = os.path.join(debug_dir, "opus_chunks.bin")
                with open(opus_path, "wb") as f:
                    f.writelines(self.debug_opus_chunks)

                logger.info(f"Saved {len(self.debug_opus_chunks)} Opus chunks: {opus_path}")

            # Save analysis summary
            summary_path = os.path.join(debug_dir, "analysis.txt")
            with open(summary_path, "w") as f:
                f.write("Streaming Debug Analysis\n")
                f.write("========================\n")
                f.write(f"Session ID: {self.session_id}\n")
                f.write(f"Total chunks processed: {self.debug_chunk_count}\n")
                f.write(f"Raw audio chunks saved: {len(self.debug_raw_chunks)}\n")
                f.write(f"Opus chunks sent: {len(self.debug_opus_chunks)}\n")
                f.write(f"Total raw bytes reported: {self.total_raw_bytes}\n")
                f.write(f"Total opus bytes sent: {self.total_opus_bytes}\n")
                if self.debug_raw_chunks:
                    total_samples = sum(len(chunk) for chunk in self.debug_raw_chunks)
                    duration = total_samples / 16000
                    f.write(f"Total audio duration: {duration:.2f} seconds\n")
                    f.write(f"Total samples: {total_samples}\n")
                    f.write(f"Calculated duration from raw bytes: {self.total_raw_bytes / 32000:.2f} seconds\n")

            logger.info(f"Debug analysis saved to: {debug_dir}")
            logger.info(f"Debug audio saved to: {debug_dir}")
            logger.info("   - raw_audio.wav: Original audio for playback/analysis")
            logger.info("   - opus_chunks.bin: Compressed Opus data sent to server")
            logger.info("   - analysis.txt: Summary statistics")

        except Exception as e:
            logger.error(f"Failed to save debug audio: {e}")

    async def disconnect(self):
        """Disconnect from server."""
        if self.websocket:
            # Save debug audio if we have data and we're disconnecting without proper completion
            if self.debug_save_audio and (self.debug_raw_chunks or self.debug_opus_chunks):
                logger.info("Saving debug audio on disconnection")
                self.save_debug_audio()
                # Clear debug collections to free memory
                self.debug_raw_chunks.clear()
                self.debug_opus_chunks.clear()
            await self.websocket.close()
            self.websocket = None
            logger.info("Disconnected from server")


# ========================= TRANSCRIPTION CLIENT =========================


class TranscriptionClient:
    """Unified client for all transcription operations - streaming and batch modes.

    Supports dual-mode architecture:
    - Streaming mode: Real-time transcription (record-and-transcribe-simultaneously)
    - Batch mode: Traditional transcription (record-then-transcribe)
    """

    def __init__(self, websocket_host: Optional[str] = None, debug_callback: Optional[Callable[[str], None]] = None):
        """Initialize transcription client.

        Args:
            websocket_host: WebSocket server host (defaults to config)
            debug_callback: Function to call for debug logging

        """
        self.websocket_host = websocket_host or config.websocket_connect_host
        self.debug_callback = debug_callback if debug_callback is not None else (lambda msg: None)

        # Circuit breaker for connection resilience
        self.circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=3, timeout_seconds=30, success_threshold=2)
        )

        # WebSocket connection details
        self.websocket_port = config.websocket_port
        self.auth_token = config.auth_token
        self.ssl_enabled = config.ssl_enabled

        # Determine protocol and URL
        protocol = "wss" if self.ssl_enabled else "ws"
        self.websocket_url = f"{protocol}://{self.websocket_host}:{self.websocket_port}"

        # Transcription mode configuration
        self.transcription_config = getattr(config, "transcription", {})
        self.default_mode = self.transcription_config.get("default_mode", "batch")
        self.mode_configs = self.transcription_config.get("modes", {})

        # Active streaming sessions for real-time mode
        self.active_streaming_sessions: dict[str, StreamingAudioClient] = {}

        self.debug_callback(f"TranscriptionClient initialized for {self.websocket_url}")
        self.debug_callback(f"Default transcription mode: {self.default_mode}")

    def get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Get SSL context for client connections"""
        ssl_context = create_ssl_context(mode="client", auto_generate=False)
        if ssl_context is None:
            raise TranscriptionConnectionError("SSL context creation failed")

        # Log the verification mode for debugging
        verify_mode = config.ssl_verify_mode.lower()
        self.debug_callback(f"SSL client configured with {verify_mode} certificate verification")

        return ssl_context

    async def send_batch_transcription(
        self, audio_file_path: str, cancel_event: Optional[threading.Event] = None, use_opus_compression: bool = True
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Send batch transcription request.

        Args:
            audio_file_path: Path to audio file for transcription
            cancel_event: Event to check for cancellation
            use_opus_compression: Whether to compress audio with Opus before sending

        Returns:
            (success, transcription_text, error_message)

        """
        if not self.circuit_breaker.can_execute():
            status = self.circuit_breaker.get_status()
            return False, None, f"Circuit breaker {status['state']} - connection unavailable"

        try:
            # Check if file exists and has content
            if not os.path.exists(audio_file_path):
                return False, None, f"Audio file not found: {audio_file_path}"

            file_size = os.path.getsize(audio_file_path)
            if file_size == 0:
                return False, None, "Audio file is empty"

            self.debug_callback(f"Sending batch transcription for {audio_file_path} ({file_size} bytes)")

            # Read audio file
            with open(audio_file_path, "rb") as f:
                audio_data = f.read()

            # Optionally compress with Opus
            metadata = None
            if use_opus_compression:
                try:
                    opus_bitrate = config.get("audio_compression.opus_bitrate", 24000)
                    opus_encoder = OpusBatchEncoder(bitrate=opus_bitrate)
                    opus_data, metadata = opus_encoder.encode_wav_to_opus(audio_data)
                    self.debug_callback(
                        f"Compressed audio: {len(audio_data)} → {len(opus_data)} bytes "
                        f"({metadata['compression_ratio']:.1f}x compression)"
                    )
                    audio_data = opus_data  # Use compressed data
                except Exception as e:
                    self.debug_callback(f"Opus compression failed, falling back to WAV: {e}")
                    metadata = None  # Fall back to uncompressed

            audio_base64 = base64.b64encode(audio_data).decode("utf-8")

            # Check for cancellation
            if cancel_event and cancel_event.is_set():
                return False, None, "Operation cancelled"

            # Create WebSocket connection
            ssl_context = self.get_ssl_context() if self.ssl_enabled else None

            async with websockets.connect(self.websocket_url, ssl=ssl_context) as websocket:
                # Wait for welcome message
                welcome_msg = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                welcome_data = json.loads(welcome_msg)

                if welcome_data.get("type") != "welcome":
                    return False, None, f"Unexpected welcome message: {welcome_data}"

                # Send transcription request
                request = {
                    "type": "transcribe",
                    "token": self.auth_token,
                    "audio_data": audio_base64,
                    "filename": os.path.basename(audio_file_path),
                    "audio_format": "opus" if metadata else "wav",
                    "metadata": metadata,
                }

                await websocket.send(json.dumps(request))
                self.debug_callback("Batch transcription request sent")

                # Wait for response with timeout
                response_msg = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                response_data = json.loads(response_msg)

                if response_data.get("type") == "transcription_complete":
                    transcription = response_data.get("text", "").strip()
                    self.circuit_breaker.record_success()
                    self.debug_callback(f"Batch transcription completed: {len(transcription)} chars")
                    return True, transcription, None

                if response_data.get("type") == "error":
                    error_msg = response_data.get("message", "Unknown server error")
                    self.circuit_breaker.record_failure()
                    return False, None, f"Server error: {error_msg}"
                self.circuit_breaker.record_failure()
                return False, None, f"Unexpected response: {response_data}"

        except asyncio.TimeoutError:
            self.circuit_breaker.record_failure()
            return False, None, "Transcription request timed out"
        except websockets.exceptions.ConnectionClosed as e:
            self.circuit_breaker.record_failure()
            return False, None, f"WebSocket connection closed: {e}"
        except Exception as e:
            self.circuit_breaker.record_failure()
            return False, None, f"Transcription failed: {e}"

    async def transcribe_batch_mode(
        self, audio_file_path: str, cancel_event: Optional[threading.Event] = None, **batch_options
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Traditional batch transcription (record-then-transcribe).

        This mode waits for recording to complete, then transcribes the entire
        audio file at once. Provides higher accuracy but higher latency.

        Args:
            audio_file_path: Path to completed audio file
            cancel_event: Event to check for cancellation
            **batch_options: Additional batch configuration

        Returns:
            (success, transcription_text, error_message)

        """
        # Get batch configuration
        batch_config = self.mode_configs.get("batch", {})
        min_duration = batch_options.get("min_recording_duration", batch_config.get("min_recording_duration", 0.5))
        max_duration = batch_options.get("max_recording_duration", batch_config.get("max_recording_duration", 300))

        self.debug_callback(f"Starting batch transcription (min: {min_duration}s, max: {max_duration}s)")

        # Validate audio file duration if needed
        try:
            if os.path.exists(audio_file_path):
                file_size = os.path.getsize(audio_file_path)
                # Rough estimate: 16kHz * 2 bytes/sample = 32000 bytes/second
                estimated_duration = (file_size - 44) / 32000  # Subtract WAV header

                if estimated_duration < min_duration:
                    return False, None, f"Recording too short: {estimated_duration:.1f}s < {min_duration}s"
                if estimated_duration > max_duration:
                    return False, None, f"Recording too long: {estimated_duration:.1f}s > {max_duration}s"

                self.debug_callback(f"Batch transcription for {estimated_duration:.1f}s of audio")
        except Exception as e:
            self.debug_callback(f"Could not validate audio duration: {e}")

        # Use existing batch transcription method
        use_opus = batch_options.get("use_opus_compression", config.get("audio_compression.enable_opus_batch", True))
        return await self.send_batch_transcription(audio_file_path, cancel_event, use_opus)

    async def transcribe_with_mode(
        self,
        audio_file_path: str,
        mode: Optional[str] = None,
        session_id: Optional[str] = None,
        cancel_event: Optional[threading.Event] = None,
        **mode_options,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Transcribe using specified mode or default configuration.

        Args:
            audio_file_path: Path to audio file
            mode: 'streaming' or 'batch' (defaults to configured default)
            session_id: Session ID for streaming mode
            cancel_event: Event to check for cancellation
            **mode_options: Mode-specific configuration options

        Returns:
            (success, transcription_text, error_message)

        """
        # Determine transcription mode
        transcription_mode = mode or self.default_mode

        self.debug_callback(f"Transcribing with mode: {transcription_mode}")

        if transcription_mode == "streaming":
            # Streaming mode is now handled directly by daemon with PipeBasedAudioStreamer
            # For TranscriptionClient, fall back to batch mode for file-based transcription
            self.debug_callback(
                "Streaming mode requested but TranscriptionClient uses batch - falling back to batch mode"
            )
            return await self.transcribe_batch_mode(audio_file_path, cancel_event, **mode_options)
        if transcription_mode == "batch":
            return await self.transcribe_batch_mode(audio_file_path, cancel_event, **mode_options)
        return False, None, f"Unknown transcription mode: {transcription_mode}"

    async def create_streaming_session(
        self, session_id: Optional[str] = None, debug_save_audio: Optional[bool] = None
    ) -> StreamingAudioClient:
        """Create and start a new streaming session.

        Args:
            session_id: Optional session ID (auto-generated if not provided)
            debug_save_audio: If True, save audio chunks for debugging (defaults to config value)

        Returns:
            Connected and started streaming client

        Raises:
            RuntimeError: If connection or session start fails

        """
        # Use config value if not explicitly provided
        if debug_save_audio is None:
            debug_save_audio = config.get("debug.save_audio", False)

        max_debug_chunks = config.get("debug.max_chunks", 1000)

        # Create streaming client with bounded debug collections
        streaming_client = StreamingAudioClient(
            self.websocket_url,
            self.auth_token,
            debug_save_audio=debug_save_audio,
            max_debug_chunks=max_debug_chunks,
        )

        # Connect and start session
        await streaming_client.connect()
        actual_session_id = await streaming_client.start_stream(session_id)

        # Track active session
        self.active_streaming_sessions[actual_session_id] = streaming_client

        return streaming_client

    async def cleanup_streaming_session(self, streaming_client: StreamingAudioClient) -> None:
        """Clean up a streaming session.

        Args:
            streaming_client: The streaming client to clean up

        """
        if streaming_client.session_id and streaming_client.session_id in self.active_streaming_sessions:
            del self.active_streaming_sessions[streaming_client.session_id]

        try:
            await streaming_client.disconnect()
        except Exception as e:
            self.debug_callback(f"Error disconnecting streaming client: {e}")

    def get_supported_modes(self) -> Dict[str, Any]:
        """Get supported transcription modes and their configurations."""
        return {
            "default_mode": self.default_mode,
            "available_modes": ["streaming", "batch"],
            "mode_configs": self.mode_configs,
            "streaming_description": "Real-time transcription (record-and-transcribe-simultaneously)",
            "batch_description": "Traditional transcription (record-then-transcribe)",
        }

    def get_connection_status(self) -> dict:
        """Get connection and circuit breaker status."""
        return {
            "websocket_url": self.websocket_url,
            "ssl_enabled": self.ssl_enabled,
            "circuit_breaker": self.circuit_breaker.get_status(),
            "transcription_modes": self.get_supported_modes(),
            "active_streaming_sessions": len(self.active_streaming_sessions),
        }


# ========================= UTILITY FUNCTIONS =========================
