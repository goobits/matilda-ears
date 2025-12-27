#!/usr/bin/env python3
"""Unified Transcription Client - Main facade for all transcription operations.

This module provides the TranscriptionClient class which serves as the main
interface for all client-side transcription operations.
"""

import threading
from typing import Optional, Any, Callable, Dict, Tuple

from .exceptions import TranscriptionConnectionError
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .streaming import StreamingAudioClient, PartialResultCallback
from .batch import BatchTranscriber
from ...core.config import get_config, setup_logging

config = get_config()
logger = setup_logging(__name__, log_filename="transcription.txt")


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
        self.token = config.jwt_token
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

        # Initialize batch transcriber
        self._batch_transcriber = BatchTranscriber(
            websocket_url=self.websocket_url,
            token=self.token,
            ssl_enabled=self.ssl_enabled,
            circuit_breaker=self.circuit_breaker,
            mode_configs=self.mode_configs,
            debug_callback=self.debug_callback,
        )

        self.debug_callback(f"TranscriptionClient initialized for {self.websocket_url}")
        self.debug_callback(f"Default transcription mode: {self.default_mode}")

    def get_ssl_context(self):
        """Get SSL context for client connections.

        Returns:
            SSL context or raises TranscriptionConnectionError if creation fails

        """
        return self._batch_transcriber.get_ssl_context()

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
        return await self._batch_transcriber.send_batch_transcription(
            audio_file_path, cancel_event, use_opus_compression
        )

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
        return await self._batch_transcriber.transcribe_batch_mode(audio_file_path, cancel_event, **batch_options)

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
        self,
        session_id: Optional[str] = None,
        debug_save_audio: Optional[bool] = None,
        on_partial_result: Optional[PartialResultCallback] = None,
    ) -> StreamingAudioClient:
        """Create and start a new streaming session.

        Args:
            session_id: Optional session ID (auto-generated if not provided)
            debug_save_audio: If True, save audio chunks for debugging (defaults to config value)
            on_partial_result: Optional callback for real-time partial results.
                The callback receives PartialResult objects with:
                - confirmed_text: Stable, agreed-upon text (won't change)
                - tentative_text: Draft text that may change with more audio
                - is_final: Whether streaming has completed

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
            self.token,
            debug_save_audio=debug_save_audio,
            max_debug_chunks=max_debug_chunks,
            on_partial_result=on_partial_result,
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
        """Get supported transcription modes and their configurations.

        Returns:
            Dictionary with mode information

        """
        return {
            "default_mode": self.default_mode,
            "available_modes": ["streaming", "batch"],
            "mode_configs": self.mode_configs,
            "streaming_description": "Real-time transcription (record-and-transcribe-simultaneously)",
            "batch_description": "Traditional transcription (record-then-transcribe)",
        }

    def get_connection_status(self) -> dict:
        """Get connection and circuit breaker status.

        Returns:
            Dictionary with connection status information

        """
        return {
            "websocket_url": self.websocket_url,
            "ssl_enabled": self.ssl_enabled,
            "circuit_breaker": self.circuit_breaker.get_status(),
            "transcription_modes": self.get_supported_modes(),
            "active_streaming_sessions": len(self.active_streaming_sessions),
        }
