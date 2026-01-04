"""Core WebSocket server class for Matilda STT.

This module contains the MatildaWebSocketServer class which is the main
server implementation. It imports handlers from the handlers module and
wires them together.
"""

import asyncio
import json
import os
import time
import traceback
import uuid
from collections import defaultdict

import websockets

from ...audio.decoder import OpusStreamDecoder
from ...core.config import get_config, setup_logging
from ...utils.ssl import create_ssl_context
from ..backends import get_backend_class
from . import handlers
from .main import start_server as _start_server
from .transcription import pcm_to_wav, send_error, transcribe_audio_from_wav

# Get config instance and setup logging
config = get_config()
logger = setup_logging(__name__, log_filename="transcription.txt")


class MatildaWebSocketServer:
    """WebSocket server for speech-to-text transcription.

    This server handles:
    - Binary WAV audio for direct transcription
    - JSON protocol for streaming audio (Opus/PCM)
    - Real-time streaming transcription via streaming framework
    - JWT authentication
    - Rate limiting per client IP
    """

    def __init__(self):
        # Get config from package namespace for patchability in tests
        from . import config as _config

        self.model_size = _config.whisper_model
        self.host = _config.websocket_bind_host
        self.port = _config.websocket_port
        # Initialize JWT token manager
        from . import TokenManager as _TokenManager
        self.token_manager = _TokenManager(_config.jwt_secret_key)

        # Initialize Backend
        self.backend_name = _config.transcription_backend
        self.backend = None
        try:
            backend_class = get_backend_class(self.backend_name)
            self.backend = backend_class()
            logger.debug(f"Using transcription backend: {self.backend_name}")
        except ValueError as e:
            logger.error(f"Failed to initialize backend: {e}")
            # Use package's sys for patchability in tests
            from . import sys as _sys
            _sys.exit(1)

        # GPU serialization: Limit concurrent transcriptions to 1 for Parakeet to prevent MPS crashes
        # This prevents overlapping Metal/MPS command buffer operations on macOS
        self.transcription_semaphore = None
        if self.backend_name == "parakeet":
            self.transcription_semaphore = asyncio.Semaphore(1)
            logger.debug("GPU serialization enabled for Parakeet")

        # Set MPS fallback for Parakeet to allow CPU fallback for unsupported ops
        if self.backend_name == "parakeet":
            os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
            logger.debug("PYTORCH_ENABLE_MPS_FALLBACK=1 set")

        # WebSocket-level session tracking (self-contained)
        self.streaming_sessions = {}  # session_id -> StreamingSession (new framework)

        # Streaming sessions managed by streaming framework

        # SSL configuration
        self.ssl_enabled = config.ssl_enabled
        self.ssl_context = None
        if self.ssl_enabled:
            self.ssl_context = self._setup_ssl_context()

        # Rate limiting: max 10 requests per minute per IP
        self.rate_limits = defaultdict(list)
        self.max_requests_per_minute = 10

        # Client tracking
        self.connected_clients = set()

        # Opus stream decoder for handling streaming audio
        self.opus_decoder = OpusStreamDecoder()

        # Track chunk counts for proper stream ending
        self.session_chunk_counts = {}  # session_id -> {"received": count, "expected": count}

        # PCM streaming sessions (for web clients sending raw PCM, not Opus)
        self.pcm_sessions = {}  # session_id -> {"samples": [], "sample_rate": int, "channels": int}

        # Sessions that are currently ending (to prevent race conditions)
        self.ending_sessions = set()  # session_ids being finalized

        # Track sessions per client for cleanup on disconnect
        self.client_sessions = {}  # client_id -> set of session_ids

        # Track binary streaming sessions per client (Opus chunks over binary frames)
        self.binary_stream_sessions = {}  # client_id -> session_id

        # Health server runner (set during start_server)
        self._health_runner = None

        # Set up message handlers dictionary
        self.message_handlers = {
            "ping": self._wrap_handler(handlers.handle_ping),
            "auth": self._wrap_handler(handlers.handle_auth),
            "transcribe": self._wrap_handler(handlers.handle_transcription),
            "start_stream": self._wrap_handler(handlers.handle_start_stream),
            "audio_chunk": self._wrap_handler(handlers.handle_audio_chunk),
            "pcm_chunk": self._wrap_handler(handlers.handle_pcm_chunk),
            "end_stream": self._wrap_handler(handlers.handle_end_stream),
        }

        protocol = "wss" if self.ssl_enabled else "ws"
        logger.debug(f"Initializing server on {protocol}://{self.host}:{self.port}")
        if self.ssl_enabled:
            logger.debug("SSL/TLS encryption enabled")

    def _wrap_handler(self, handler):
        """Wrap a handler to inject self as the first argument.

        Args:
            handler: The handler function to wrap

        Returns:
            Wrapped handler that passes self as first argument

        """

        async def wrapped(websocket, data, client_ip, client_id):
            return await handler(self, websocket, data, client_ip, client_id)

        return wrapped

    def _setup_ssl_context(self):
        """Set up SSL context for secure WebSocket connections."""
        ssl_context = create_ssl_context(mode="server", auto_generate=True)
        if ssl_context is None:
            logger.error("Falling back to non-SSL mode")
            self.ssl_enabled = False
        return ssl_context

    async def load_model(self):
        """Load transcription model asynchronously."""
        try:
            await self.backend.load()
        except Exception as e:
            logger.exception(f"Failed to load backend model: {e}")
            logger.exception(traceback.format_exc())
            raise

    def check_rate_limit(self, client_ip: str) -> bool:
        """Check if client is within rate limits.

        Args:
            client_ip: Client IP address

        Returns:
            True if within limits, False if rate limited

        """
        now = time.time()
        minute_ago = now - 60

        # Clean old entries
        self.rate_limits[client_ip] = [timestamp for timestamp in self.rate_limits[client_ip] if timestamp > minute_ago]

        # Check if under limit
        if len(self.rate_limits[client_ip]) >= self.max_requests_per_minute:
            return False

        # Add current request
        self.rate_limits[client_ip].append(now)
        return True

    async def handle_client(self, websocket, path=None):
        """Handle individual WebSocket client connections.

        Args:
            websocket: The WebSocket connection
            path: Optional path (for compatibility)

        """
        client_id = str(uuid.uuid4())[:8]
        client_ip = websocket.remote_address[0]

        try:
            self.connected_clients.add(websocket)
            logger.debug(f"Client {client_id} connected from {client_ip}")

            # Send welcome message
            await websocket.send(
                json.dumps(
                    {
                        "type": "welcome",
                        "message": "Connected to Matilda WebSocket Server",
                        "client_id": client_id,
                        "server_ready": self.backend.is_ready,
                    }
                )
            )

            async for message in websocket:
                try:
                    # Handle binary messages (raw WAV audio data)
                    if isinstance(message, bytes):
                        if client_id in self.binary_stream_sessions:
                            await handlers.handle_binary_stream_chunk(
                                self, websocket, message, client_ip, client_id
                            )
                        else:
                            await handlers.handle_binary_audio(self, websocket, message, client_ip, client_id)
                    else:
                        # Handle JSON messages (existing protocol)
                        data = json.loads(message)
                        await self.process_message(websocket, data, client_ip, client_id)

                except json.JSONDecodeError:
                    await send_error(websocket, "Invalid JSON format")
                except Exception as e:
                    logger.exception(f"Error processing message from {client_id}: {e}")
                    await send_error(websocket, f"Processing error: {e!s}")

        except websockets.exceptions.ConnectionClosed:
            logger.debug(f"Client {client_id} disconnected")
        except Exception as e:
            logger.exception(f"Error handling client {client_id}: {e}")
            logger.exception(traceback.format_exc())
        finally:
            self.connected_clients.discard(websocket)
            self.binary_stream_sessions.pop(client_id, None)
            # Clean up any streaming sessions for this client
            if client_id in self.client_sessions:
                orphaned_sessions = self.client_sessions.pop(client_id, set())
                for session_id in orphaned_sessions:
                    # Clean up all session state
                    self.pcm_sessions.pop(session_id, None)
                    self.opus_decoder.remove_session(session_id)
                    self.session_chunk_counts.pop(session_id, None)
                    self.ending_sessions.discard(session_id)
                    # Abort new streaming framework session if active
                    if session_id in self.streaming_sessions:
                        try:
                            session = self.streaming_sessions.pop(session_id)
                            asyncio.create_task(session.abort())
                        except Exception:
                            # Ignore errors during cleanup
                            pass
                if orphaned_sessions:
                    logger.debug(f"Client {client_id}: Cleaned up {len(orphaned_sessions)} orphaned session(s)")
            logger.debug(f"Client {client_id} removed")

    async def handle_reload(self, websocket, data: dict, client_ip: str, client_id: str):
        """Handle configuration reload request."""
        # Verify it's a local request or authorized admin
        if client_ip not in ["127.0.0.1", "::1", "localhost"]:
             await self.send_error(websocket, "Unauthorized: Reload only allowed from localhost")
             return

        try:
            logger.info("Reloading configuration...")
            # Reload config file
            from ...core.config import get_config, ConfigLoader
            
            # Force reload the singleton
            import matilda_ears.core.config
            matilda_ears.core.config._config_loader = ConfigLoader()
            
            # Update local references if any (most use the global get_config())
            global config
            config = get_config()
            
            await websocket.send(json.dumps({
                "type": "reload_response",
                "status": "ok", 
                "message": "Configuration reloaded"
            }))
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.exception("Failed to reload configuration")
            await self.send_error(websocket, f"Reload failed: {e}")

    async def process_message(self, websocket, data: dict, client_ip: str, client_id: str):
        """Process different types of messages from clients.

        Args:
            websocket: The WebSocket connection
            data: Parsed JSON message data
            client_ip: Client IP address
            client_id: Client identifier

        """
        message_type = data.get("type")

        # Handle reload explicitly since it's new
        if message_type == "reload":
            await self.handle_reload(websocket, data, client_ip, client_id)
            return

        # Get message handler from the dictionary
        handler = self.message_handlers.get(message_type)
        if handler:
            await handler(websocket, data, client_ip, client_id)
        else:
            await send_error(websocket, f"Unknown message type: {message_type}")

    # Expose transcription methods on the server instance for backward compatibility
    async def transcribe_audio_from_wav(self, wav_data: bytes, client_id: str):
        """Transcribe audio from WAV data.

        Args:
            wav_data: WAV audio data
            client_id: Client identifier

        Returns:
            (success, text, info) tuple

        """
        return await transcribe_audio_from_wav(self, wav_data, client_id)

    def _pcm_to_wav(self, samples, sample_rate: int, channels: int = 1) -> bytes:
        """Convert PCM samples to WAV format.

        Args:
            samples: PCM samples as numpy array
            sample_rate: Sample rate in Hz
            channels: Number of channels

        Returns:
            WAV data as bytes

        """
        return pcm_to_wav(samples, sample_rate, channels)

    async def send_error(self, websocket, message: str):
        """Send error message to client.

        Args:
            websocket: The WebSocket connection
            message: Error message

        """
        await send_error(websocket, message)

    async def start_server(self, host=None, port=None):
        """Start the WebSocket server.

        Args:
            host: Host to bind to (optional)
            port: Port to bind to (optional)

        """
        await _start_server(self, host, port)


# Enhanced server with dual-mode support
class EnhancedWebSocketServer(MatildaWebSocketServer):
    """Enhanced WebSocket server with full dual-mode support."""

    def __init__(self):
        super().__init__()
        logger.debug("Enhanced WebSocket server initialized with dual-mode support")


# Use enhanced server as default
WebSocketTranscriptionServer = EnhancedWebSocketServer
