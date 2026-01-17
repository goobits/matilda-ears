#!/usr/bin/env python3
"""WebSocket client for streaming Opus audio to server.

This module provides the StreamingAudioClient class for real-time audio streaming
to the transcription server.
"""

import asyncio
import os
import json
import base64
import ssl
import wave
import tempfile
from dataclasses import dataclass
from collections.abc import Callable
import numpy as np
import websockets

from .exceptions import TranscriptionConnectionError, StreamingError
from ....audio.encoder import OpusEncoder
from ....core.config import setup_logging

logger = setup_logging(__name__, log_filename="transcription.txt")


def _unwrap_envelope(data: dict) -> dict:
    if data.get("service") == "ears" and data.get("task"):
        if data.get("error"):
            error = data.get("error", {})
            return {
                "type": "error",
                "message": error.get("message"),
                "error": error,
            }
        payload = data.get("result") or {}
        if "type" not in payload:
            payload = {**payload, "type": data.get("task")}
        return payload
    return data


@dataclass
class PartialResult:
    """Represents a partial transcription result from streaming.

    Attributes:
        confirmed_text: Stable text that won't change (LocalAgreement confirmed)
        tentative_text: Draft text that may change with more audio
        is_final: Whether this is the final result
        session_id: The streaming session ID
        full_text: Concatenation of confirmed + tentative

    """

    confirmed_text: str = ""
    tentative_text: str = ""
    is_final: bool = False
    session_id: str = ""
    full_text: str = ""

    @classmethod
    def from_message(cls, data: dict) -> "PartialResult":
        """Create PartialResult from server message."""
        confirmed = data.get("confirmed_text", "")
        tentative = data.get("tentative_text", "")
        full_text = (confirmed + " " + tentative).strip()
        return cls(
            confirmed_text=confirmed,
            tentative_text=tentative,
            is_final=data.get("is_final", False),
            session_id=data.get("session_id", ""),
            full_text=full_text,
        )


# Type alias for partial result callback
PartialResultCallback = Callable[[PartialResult], None]


class StreamingAudioClient:
    """WebSocket client for streaming Opus audio to server.

    This class provides a direct interface for streaming audio to the transcription
    server. It is used by StreamHandler and other components that need real-time
    audio streaming capabilities.

    The client supports real-time partial results via an optional callback. When
    provided, the callback receives PartialResult objects with:
    - confirmed_text: Stable, agreed-upon text (won't change)
    - tentative_text: Draft text that may change with more audio
    - is_final: Whether streaming has completed
    """

    def __init__(
        self,
        websocket_url: str,
        token: str,
        debug_save_audio: bool = False,
        max_debug_chunks: int = 1000,
        on_partial_result: PartialResultCallback | None = None,
    ):
        """Initialize streaming client.

        Args:
            websocket_url: WebSocket server URL
            token: JWT token
            debug_save_audio: If True, save audio chunks for debugging
            max_debug_chunks: Maximum number of debug chunks to keep (default: 1000)
            on_partial_result: Optional callback for real-time partial results

        """
        self.websocket_url = websocket_url
        self.token = token
        self.websocket = None
        self.session_id = None
        self.encoder = OpusEncoder()

        # Partial result callback for real-time updates
        self.on_partial_result = on_partial_result
        self._listener_task: asyncio.Task | None = None
        self._stop_listener = asyncio.Event()
        self._pending_messages: asyncio.Queue = asyncio.Queue()

        # Track latest partial result for callers that don't use callback
        self._latest_partial: PartialResult | None = None

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

    async def _listen_for_partial_results(self):
        """Background task to listen for partial results during streaming.

        This runs concurrently with audio sending and invokes the callback
        when partial_result messages are received.
        """
        logger.debug("Starting partial result listener")
        try:
            while not self._stop_listener.is_set():
                if self._is_websocket_closed():
                    logger.debug("WebSocket closed, stopping listener")
                    break

                try:
                    # Use wait_for to allow periodic checking of stop flag
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=0.5,
                    )
                    data = _unwrap_envelope(json.loads(message))
                    msg_type = data.get("type", "")

                    if msg_type == "partial_result":
                        partial = PartialResult.from_message(data)
                        self._latest_partial = partial

                        # Invoke callback if provided
                        if self.on_partial_result:
                            try:
                                self.on_partial_result(partial)
                            except Exception as e:
                                logger.error(f"Error in partial result callback: {e}")

                        logger.debug(
                            f"Partial result: confirmed='{partial.confirmed_text[:50]}...' "
                            f"tentative='{partial.tentative_text[:30]}...'"
                        )
                    else:
                        # Queue non-partial messages for end_stream to process
                        await self._pending_messages.put(data)
                        logger.debug(f"Queued message type: {msg_type}")

                except TimeoutError:
                    # Normal timeout, continue loop
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.debug("Connection closed during listen")
                    break
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON received: {e}")
                    continue

        except Exception as e:
            logger.error(f"Listener error: {e}")
        finally:
            logger.debug("Partial result listener stopped")

    def _start_listener(self):
        """Start the background listener task."""
        self._stop_listener.clear()
        self._listener_task = asyncio.create_task(self._listen_for_partial_results())

    async def _stop_listener_task(self):
        """Stop the background listener task."""
        self._stop_listener.set()
        if self._listener_task:
            try:
                await asyncio.wait_for(self._listener_task, timeout=2.0)
            except TimeoutError:
                self._listener_task.cancel()
                try:
                    await self._listener_task
                except asyncio.CancelledError:
                    pass
            self._listener_task = None

    @property
    def latest_partial_result(self) -> PartialResult | None:
        """Get the most recent partial result received during streaming."""
        return self._latest_partial

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
            welcome_data = _unwrap_envelope(json.loads(welcome))
            logger.debug(f"Server welcome: {welcome_data}")

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise

    async def start_stream(self, session_id=None) -> str:
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
        self._latest_partial = None  # Reset for new session

        # Send start stream message
        message = {
            "type": "start_stream",
            "token": self.token,
            "session_id": session_id,
            "sample_rate": self.encoder.sample_rate,
            "channels": self.encoder.channels,
        }

        await self.websocket.send(json.dumps(message))

        # Wait for acknowledgment
        response = await self.websocket.recv()
        response_data = _unwrap_envelope(json.loads(response))

        if response_data.get("type") == "stream_started":
            logger.info(f"Stream started: {session_id}")

            # Start background listener for partial results
            self._start_listener()

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
                    f"SENT opus packet #{self.sent_opus_packets}: {len(audio_data)} samples -> {len(opus_data)} bytes"
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
            Transcription result from server with fields:
            - success: bool
            - confirmed_text: str (stable text from LocalAgreement)
            - tentative_text: str (draft text, empty in final result)
            - is_final: bool (always True for end_stream result)

        """
        if not self.session_id:
            raise RuntimeError("No active stream session")

        # Stop the background listener first
        await self._stop_listener_task()

        # Check if we had streaming errors
        if self._last_streaming_error:
            logger.warning(f"Stream had errors during transmission: {self._last_streaming_error}")

        # Check if WebSocket connection is still valid
        if not self.websocket or self._is_websocket_closed():
            logger.error("WebSocket connection is None or closed - cannot end stream properly")
            return {
                "success": False,
                "text": "",
                "confirmed_text": "",
                "tentative_text": "",
                "is_final": True,
                "message": "WebSocket connection lost",
            }

        # CRITICAL: Flush any remaining audio from encoder buffer
        logger.info("FLUSHING encoder buffer")
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
                return self._error_response(f"Connection closed during finalization: {e}")
            except Exception as e:
                logger.error(f"Failed to send final chunk: {e}")
                # Save debug audio on failure
                if self.debug_save_audio:
                    self.save_debug_audio()
                    # Clear debug collections to free memory
                    self.debug_raw_chunks.clear()
                    self.debug_opus_chunks.clear()
                return self._error_response(f"Failed to send final chunk: {e}")
            logger.info(
                f"SENT final flushed opus packet #{self.sent_opus_packets} ({len(final_chunk)} bytes). "
                f"Final totals: {self.total_raw_bytes} raw, {self.total_opus_bytes} opus"
            )
        else:
            logger.info("No data to flush from encoder buffer")

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
            return self._error_response(f"Connection closed during stream end: {e}")
        except Exception as e:
            logger.error(f"Failed to send end stream message: {e}")
            # Save debug audio on failure
            if self.debug_save_audio:
                self.save_debug_audio()
                # Clear debug collections to free memory
                self.debug_raw_chunks.clear()
                self.debug_opus_chunks.clear()
            return self._error_response(f"Failed to send end stream message: {e}")

        # Wait for transcription result - check pending messages first
        response_data = None

        # Check if we already received the result during listening
        while not self._pending_messages.empty():
            try:
                queued = self._pending_messages.get_nowait()
                if queued.get("type") in (
                    "transcription_result",
                    "stream_ended",
                    "transcription_complete",
                    "stream_transcription_complete",
                ):
                    response_data = queued
                    break
            except asyncio.QueueEmpty:
                break

        # If not in queue, wait for it from websocket
        if response_data is None:
            try:
                response = await self.websocket.recv()
                response_data = _unwrap_envelope(json.loads(response))
            except websockets.exceptions.ConnectionClosed as e:
                logger.error(f"Connection closed while receiving transcription result: {e}")
                # Save debug audio on connection failure
                if self.debug_save_audio:
                    self.save_debug_audio()
                    # Clear debug collections to free memory
                    self.debug_raw_chunks.clear()
                    self.debug_opus_chunks.clear()
                return self._error_response(f"Connection closed during result reception: {e}")
            except Exception as e:
                logger.error(f"Failed to receive transcription result: {e}")
                # Save debug audio on failure
                if self.debug_save_audio:
                    self.save_debug_audio()
                    # Clear debug collections to free memory
                    self.debug_raw_chunks.clear()
                    self.debug_opus_chunks.clear()
                return self._error_response(f"Failed to receive transcription result: {e}")

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

        # Normalize response to include new schema fields
        return self._normalize_response(response_data)

    def _error_response(self, message: str) -> dict:
        """Create a standardized error response with new schema fields.

        Args:
            message: Error message to include

        Returns:
            Error response dict with all expected fields

        """
        return {
            "success": False,
            "confirmed_text": "",
            "tentative_text": "",
            "is_final": True,
            "message": message,
        }

    def _normalize_response(self, response_data: dict) -> dict:
        """Normalize server response to include all expected schema fields.

        Args:
            response_data: Raw response from server

        Returns:
            Normalized response with all expected fields

        """
        # Extract text from expected schema
        is_error = response_data.get("type") == "error" or response_data.get("error") is not None
        confirmed = response_data.get("confirmed_text", "")
        tentative = response_data.get("tentative_text", "")
        normalized = {**response_data}
        normalized.pop("text", None)

        return {
            # Preserve all original fields except text
            **normalized,
            # Ensure new schema fields exist
            "confirmed_text": confirmed,
            "tentative_text": tentative,
            "is_final": response_data.get("is_final", True),
            "success": response_data.get("success", not is_error),
        }

    def save_debug_audio(self):
        """Save debug audio data for analysis."""
        import time as time_module

        try:
            timestamp = int(time_module.time())
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
        # Stop the listener task if running
        await self._stop_listener_task()

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
