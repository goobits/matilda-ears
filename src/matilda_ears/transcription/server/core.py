"""Core WebSocket server class for Matilda STT.

This module contains the MatildaWebSocketServer class which is the main
server implementation. It imports handlers from the handlers module and
wires them together.
"""

import asyncio
import concurrent.futures
import json
import os
import time
import traceback
import uuid
from collections import defaultdict
from ipaddress import ip_address, ip_network
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import websockets

from ...core.config import get_config, setup_logging
from ...utils.ssl import create_ssl_context
from ..backends import get_backend_class
from . import handlers
from .internal.audio_utils import pcm_to_wav
from .internal.session_registry import ServerSession, SessionRegistry
from .internal.transcription import send_envelope, send_error, transcribe_audio_from_wav

if TYPE_CHECKING:
    from aiohttp.web import AppRunner

    from ...core.token_manager import TokenManager

# Get config instance and setup logging
config = get_config()
logger = setup_logging(__name__, log_filename="transcription.txt")


def _request_headers(websocket):
    headers = getattr(websocket, "request_headers", None)
    if headers is not None:
        return headers
    request = getattr(websocket, "request", None)
    return getattr(request, "headers", None)


def _request_path(websocket) -> str:
    request = getattr(websocket, "request", None)
    if request is not None and getattr(request, "path", None):
        return str(request.path)
    return str(getattr(websocket, "path", "") or "")


def _connection_token(websocket) -> str | None:
    headers = _request_headers(websocket)
    authorization = headers.get("Authorization") if headers else None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        if token:
            return token

    query = parse_qs(urlsplit(_request_path(websocket)).query)
    for key in ("api_token", "token"):
        values = query.get(key)
        if values and values[0]:
            return values[0]
    return None


def _is_trusted_proxy(peer_ip: str, trusted_proxies: list[str]) -> bool:
    try:
        peer = ip_address(peer_ip.split("%", maxsplit=1)[0])
    except ValueError:
        return False

    for value in trusted_proxies:
        try:
            if peer in ip_network(value, strict=False):
                return True
        except ValueError:
            logger.warning("Ignoring invalid trusted proxy entry: %s", value)
    return False


def _client_ip(websocket, trusted_proxies: list[str]) -> str:
    remote_address = getattr(websocket, "remote_address", None)
    peer_ip = str(remote_address[0]) if remote_address else "unknown"
    if not _is_trusted_proxy(peer_ip, trusted_proxies):
        return peer_ip

    headers = _request_headers(websocket)
    forwarded = headers.get("X-Forwarded-For") if headers else None
    if not forwarded:
        return peer_ip
    candidate = forwarded.split(",", maxsplit=1)[0].strip()
    try:
        ip_address(candidate.split("%", maxsplit=1)[0])
    except ValueError:
        logger.warning("Ignoring invalid X-Forwarded-For address from trusted proxy: %s", candidate)
        return peer_ip
    return candidate


class MatildaWebSocketServer:
    """WebSocket server for speech-to-text transcription.

    This server handles:
    - Binary WAV audio for direct transcription
    - JSON protocol for streaming audio (Opus/PCM)
    - Real-time streaming transcription via streaming framework
    - JWT authentication
    - Rate limiting per client IP
    """

    def __init__(self, token_manager: "TokenManager | None" = None):
        # Get config from package namespace for patchability in tests
        from . import config as _config

        self.model_size = _config.whisper_model
        self.host = _config.websocket_bind_host
        self.port = _config.websocket_port
        # Initialize JWT token manager
        from . import TokenManager as _TokenManager

        self.token_manager = token_manager if token_manager is not None else _TokenManager(_config.jwt_secret_key)

        # Initialize centralized auth policy
        from ...core.auth import AuthPolicy

        self.auth = AuthPolicy(self.token_manager)

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

        try:
            max_workers = 1 if self.backend_name == "parakeet" else int(config.get("transcription.max_workers", 2))
        except (TypeError, ValueError):
            max_workers = 2
        self.transcription_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, max_workers), thread_name_prefix="EarsTranscribe"
        )
        self.transcription_executor_semaphore = asyncio.Semaphore(max(1, max_workers))

        # SSL configuration
        self.ssl_enabled = config.ssl_enabled
        self.ssl_context = None
        if self.ssl_enabled:
            self.ssl_context = self._setup_ssl_context()

        # Rate limiting: max 10 requests per minute per IP
        self.rate_limits = defaultdict(list)
        self.max_requests_per_minute = 10
        self._last_rate_limit_cleanup = 0.0

        # Client tracking
        self.connected_clients = set()
        self.authenticated_clients = {}
        trusted_proxies = getattr(_config, "websocket_trusted_proxies", [])
        self.trusted_proxies = trusted_proxies if isinstance(trusted_proxies, list) else []

        self.sessions = SessionRegistry()

        self.wake_word_detector = None

        # Health server runner (set during start_server)
        self._health_runner: AppRunner | None = None

        self.transcriptions_started = 0
        self.transcriptions_completed = 0
        self.transcriptions_failed = 0
        self.transcriptions_timed_out = 0
        self.transcriptions_inflight = 0

        # Set up message handlers dictionary
        self.message_handlers = {
            "ping": self._wrap_handler(handlers.handle_ping),
            "auth": self._wrap_handler(handlers.handle_auth),
            "generate_token": self._wrap_handler(handlers.handle_generate_token),
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
        if self.auth._is_localhost(client_ip):
            return True

        now = time.time()
        minute_ago = now - 60
        self._cleanup_rate_limits(now)

        # Clean old entries
        self.rate_limits[client_ip] = [timestamp for timestamp in self.rate_limits[client_ip] if timestamp > minute_ago]

        # Check if under limit
        if len(self.rate_limits[client_ip]) >= self.max_requests_per_minute:
            return False

        # Add current request
        self.rate_limits[client_ip].append(now)
        return True

    def _cleanup_rate_limits(self, now: float | None = None) -> None:
        """Prune inactive rate-limit buckets so remote IP churn cannot grow forever."""
        now = time.time() if now is None else now
        if now - self._last_rate_limit_cleanup < 60:
            return

        minute_ago = now - 60
        self._last_rate_limit_cleanup = now
        for ip, timestamps in list(self.rate_limits.items()):
            recent = [timestamp for timestamp in timestamps if timestamp > minute_ago]
            if recent:
                self.rate_limits[ip] = recent
            else:
                self.rate_limits.pop(ip, None)

    async def handle_client(self, websocket, path=None):
        """Handle individual WebSocket client connections.

        Args:
            websocket: The WebSocket connection
            path: Optional path (for compatibility)

        """
        client_id = str(uuid.uuid4())[:8]
        client_ip = _client_ip(websocket, self.trusted_proxies)

        try:
            self.connected_clients.add(websocket)
            connection_auth = self.auth.check(_connection_token(websocket), client_ip)
            if connection_auth.authorized:
                self.authenticated_clients[client_id] = connection_auth
            logger.debug(f"Client {client_id} connected from {client_ip}")

            # Send welcome message
            await send_envelope(
                websocket,
                "welcome",
                {
                    "type": "welcome",
                    "message": "Connected to Matilda WebSocket Server",
                    "client_id": client_id,
                    "server_ready": self.backend.is_ready,
                    "authenticated": connection_auth.authorized,
                },
            )

            async for message in websocket:
                try:
                    # Handle binary messages (raw WAV audio data)
                    if isinstance(message, bytes):
                        if client_id not in self.authenticated_clients:
                            await send_error(websocket, "Authentication required", code="unauthorized")
                            continue
                        if self.sessions.binary_for_client(client_id) is not None:
                            await handlers.handle_binary_stream_chunk(self, websocket, message, client_ip, client_id)
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
                    await send_error(websocket, f"Processing error: {e!s}", code="internal_error", retryable=True)

        except websockets.exceptions.ConnectionClosed:
            logger.debug(f"Client {client_id} disconnected")
        except Exception as e:
            logger.exception(f"Error handling client {client_id}: {e}")
            logger.exception(traceback.format_exc())
        finally:
            self.connected_clients.discard(websocket)
            self.authenticated_clients.pop(client_id, None)
            orphaned_sessions = self.sessions.pop_client(client_id)
            for session in orphaned_sessions:
                try:
                    await self._cleanup_server_session(session)
                except Exception as e:
                    logger.debug(f"Client {client_id}: Session cleanup failed for {session.session_id}: {e}")
            if orphaned_sessions:
                logger.debug(f"Client {client_id}: Cleaned up {len(orphaned_sessions)} orphaned session(s)")
            logger.debug(f"Client {client_id} removed")

    async def _cleanup_session_state(self, session_id: str) -> None:
        """Release all server-side state associated with a streaming session."""
        session = self.sessions.pop(session_id)
        if session is not None:
            await self._cleanup_server_session(session)

    async def _cleanup_server_session(self, session: ServerSession) -> None:
        if session.streaming is not None:
            await self._cleanup_streaming_session(session.streaming)

    async def _cleanup_streaming_session(self, session) -> None:
        """Release streaming session resources without raising."""
        try:
            if hasattr(session, "abort"):
                await session.abort()
                return
            if hasattr(session, "reset"):
                await session.reset()
                return
            if hasattr(session, "finalize"):
                await session.finalize()
        except Exception:
            # Best-effort cleanup only; caller handles logging.
            pass

    async def handle_reload(self, websocket, data: dict, client_ip: str, client_id: str):
        """Handle configuration reload request."""
        # Verify it's a local request or authorized admin
        if client_ip not in ["127.0.0.1", "::1", "localhost"]:
            await self.send_error(websocket, "Unauthorized: Reload only allowed from localhost", code="unauthorized")
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

            await send_envelope(
                websocket,
                "reload_response",
                {"type": "reload_response", "status": "ok", "message": "Configuration reloaded"},
            )
            logger.info("Configuration reloaded successfully")

        except Exception as e:
            logger.exception("Failed to reload configuration")
            await self.send_error(websocket, f"Reload failed: {e}", code="internal_error", retryable=True)

    async def process_message(self, websocket, data: dict, client_ip: str, client_id: str):
        """Process different types of messages from clients.

        Args:
            websocket: The WebSocket connection
            data: Parsed JSON message data
            client_ip: Client IP address
            client_id: Client identifier

        """
        message_type = data.get("type")

        if message_type not in {"ping", "auth", "generate_token"}:
            auth_result = self._authenticate_client(client_id, client_ip, data.get("token"))
            if not auth_result.authorized:
                await send_error(websocket, "Authentication required", code="unauthorized")
                return

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

    def _authenticate_client(self, client_id: str, client_ip: str, token: str | None = None):
        existing = self.authenticated_clients.get(client_id)
        if existing is not None:
            return existing

        result = self.auth.check(token, client_ip)
        if result.authorized:
            self.authenticated_clients[client_id] = result
        return result

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

    async def send_error(self, websocket, message: str, code: str = "bad_request", retryable: bool = False):
        """Send error message to client.

        Args:
            websocket: The WebSocket connection
            message: Error message

        """
        await send_error(websocket, message, code=code, retryable=retryable)

    async def start_server(self, host=None, port=None):
        """Start the WebSocket server.

        Args:
            host: Host to bind to (optional)
            port: Port to bind to (optional)

        """
        # Imported lazily to avoid circular import during module bootstrap.
        from .main import start_server

        await start_server(self, host, port)

    def close(self) -> None:
        self.transcription_executor.shutdown(wait=False, cancel_futures=True)
        close = getattr(self.token_manager, "close", None)
        if close is not None:
            close()


EnhancedWebSocketServer = MatildaWebSocketServer
WebSocketTranscriptionServer = MatildaWebSocketServer
