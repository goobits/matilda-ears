#!/usr/bin/env python3
"""Batch transcription functionality.

This module provides batch transcription methods that are used by the
TranscriptionClient for traditional record-then-transcribe workflows.
"""

import os
import asyncio
import json
import base64
import ssl
import threading
import websockets
from typing import Optional, Tuple

from .circuit_breaker import CircuitBreaker
from ...utils.ssl import create_ssl_context
from ...audio.opus_batch import OpusBatchEncoder
from ...core.config import get_config, setup_logging

config = get_config()
logger = setup_logging(__name__, log_filename="transcription.txt")


class BatchTranscriber:
    """Handles batch transcription operations.

    This class encapsulates the batch transcription logic, providing methods
    for sending audio files to the transcription server.
    """

    def __init__(
        self,
        websocket_url: str,
        auth_token: str,
        ssl_enabled: bool,
        circuit_breaker: CircuitBreaker,
        mode_configs: dict,
        debug_callback=None,
    ):
        """Initialize batch transcriber.

        Args:
            websocket_url: WebSocket server URL
            auth_token: Authentication token
            ssl_enabled: Whether SSL is enabled
            circuit_breaker: Circuit breaker instance for connection resilience
            mode_configs: Mode configuration dictionary
            debug_callback: Optional debug callback function

        """
        self.websocket_url = websocket_url
        self.auth_token = auth_token
        self.ssl_enabled = ssl_enabled
        self.circuit_breaker = circuit_breaker
        self.mode_configs = mode_configs
        self.debug_callback = debug_callback if debug_callback is not None else (lambda msg: None)

    def get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Get SSL context for client connections.

        Returns:
            SSL context or None if SSL is disabled

        """
        ssl_context = create_ssl_context(mode="client", auto_generate=False)
        if ssl_context is None:
            from .exceptions import TranscriptionConnectionError

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
                        f"Compressed audio: {len(audio_data)} -> {len(opus_data)} bytes "
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
