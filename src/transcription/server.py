#!/usr/bin/env python3
"""WebSocket Matilda Server - Enables Mac clients to connect via WebSocket for speech-to-text
Runs alongside the existing TCP server for local Ubuntu clients
"""
import os
import sys

# Check for management token
if os.environ.get("MATILDA_MANAGEMENT_TOKEN") != "managed-by-matilda-system":
    print("❌ This server must be started via ./server.py")
    print("   Use: ./server.py start-ws")
    sys.exit(1)

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

# Environment setup for server
if os.environ.get("WEBSOCKET_SERVER_IP"):
    os.environ["WEBSOCKET_SERVER_HOST"] = os.environ["WEBSOCKET_SERVER_IP"]

# All imports after path and environment setup
import asyncio  # noqa: E402
import websockets  # noqa: E402
import json  # noqa: E402
import base64  # noqa: E402
import tempfile  # noqa: E402
import traceback  # noqa: E402
import time  # noqa: E402
from collections import defaultdict  # noqa: E402
import uuid  # noqa: E402
from typing import Tuple  # noqa: E402
from aiohttp import web  # noqa: E402
from ..core.config import get_config, setup_logging  # noqa: E402
from ..core.token_manager import TokenManager  # noqa: E402
from ..audio.decoder import OpusStreamDecoder  # noqa: E402
from ..audio.opus_batch import OpusBatchDecoder  # noqa: E402
from ..utils.ssl import create_ssl_context  # noqa: E402
from ..text_formatting.formatter import format_transcription  # noqa: E402
from .backends import get_backend_class  # noqa: E402

# Get config instance and setup logging
config = get_config()
logger = setup_logging(__name__, log_filename="transcription.txt")


class MatildaWebSocketServer:
    def __init__(self):
        self.model_size = config.whisper_model
        self.host = config.websocket_bind_host
        self.port = config.websocket_port
        self.auth_token = config.auth_token  # Keep for backward compatibility
        # Initialize JWT token manager
        self.token_manager = TokenManager(config.jwt_secret_key)

        # Initialize Backend
        self.backend_name = config.transcription_backend
        self.backend = None
        try:
            backend_class = get_backend_class(self.backend_name)
            self.backend = backend_class()
            logger.info(f"Using transcription backend: {self.backend_name}")
        except ValueError as e:
            logger.error(f"Failed to initialize backend: {e}")
            sys.exit(1)

        # GPU serialization: Limit concurrent transcriptions to 1 for Parakeet to prevent MPS crashes
        # This prevents overlapping Metal/MPS command buffer operations on macOS
        self.transcription_semaphore = None
        if self.backend_name == "parakeet":
            self.transcription_semaphore = asyncio.Semaphore(1)
            logger.info("GPU serialization enabled: Only 1 concurrent transcription for Parakeet (prevents MPS crashes)")

        # Set MPS fallback for Parakeet to allow CPU fallback for unsupported ops
        if self.backend_name == "parakeet":
            os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
            logger.info("PYTORCH_ENABLE_MPS_FALLBACK=1 set for Parakeet backend")

        # WebSocket-level session tracking (self-contained)
        self.streaming_sessions = {}  # session_id -> session_info

        # Track which sessions are using backend streaming (real-time transcription)
        self.backend_streaming_sessions = set()  # session_ids using backend.process_chunk()

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

        # Set up message handlers dictionary
        self.message_handlers = {
            "ping": self.handle_ping,
            "auth": self.handle_auth,
            "transcribe": self.handle_transcription,
            "start_stream": self.handle_start_stream,
            "audio_chunk": self.handle_audio_chunk,
            "end_stream": self.handle_end_stream,
        }

        protocol = "wss" if self.ssl_enabled else "ws"
        logger.info(f"Initializing WebSocket Matilda Server on {protocol}://{self.host}:{self.port}")
        logger.info("Self-contained session management enabled")
        if self.ssl_enabled:
            logger.info("SSL/TLS encryption enabled")

    def _setup_ssl_context(self):
        """Set up SSL context for secure WebSocket connections"""
        ssl_context = create_ssl_context(mode="server", auto_generate=True)
        if ssl_context is None:
            logger.error("Falling back to non-SSL mode")
            self.ssl_enabled = False
        return ssl_context

    async def load_model(self):
        """Load transcription model asynchronously"""
        try:
            await self.backend.load()
        except Exception as e:
            logger.exception(f"Failed to load backend model: {e}")
            logger.exception(traceback.format_exc())
            raise

    def check_rate_limit(self, client_ip):
        """Check if client is within rate limits"""
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
        """Handle individual WebSocket client connections"""
        client_id = str(uuid.uuid4())[:8]
        client_ip = websocket.remote_address[0]

        try:
            self.connected_clients.add(websocket)
            logger.info(f"Client {client_id} connected from {client_ip}")

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
                        await self.handle_binary_audio(websocket, message, client_ip, client_id)
                    else:
                        # Handle JSON messages (existing protocol)
                        data = json.loads(message)
                        await self.process_message(websocket, data, client_ip, client_id)

                except json.JSONDecodeError:
                    await self.send_error(websocket, "Invalid JSON format")
                except Exception as e:
                    logger.exception(f"Error processing message from {client_id}: {e}")
                    await self.send_error(websocket, f"Processing error: {e!s}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected normally")
        except Exception as e:
            logger.exception(f"Error handling client {client_id}: {e}")
            logger.exception(traceback.format_exc())
        finally:
            self.connected_clients.discard(websocket)
            logger.info(f"Client {client_id} removed from active connections")

    async def process_message(self, websocket, data, client_ip, client_id):
        """Process different types of messages from clients"""
        message_type = data.get("type")

        # Get message handler from the dictionary
        handler = self.message_handlers.get(message_type)
        if handler:
            await handler(websocket, data, client_ip, client_id)
        else:
            await self.send_error(websocket, f"Unknown message type: {message_type}")

    async def transcribe_audio_from_wav(self, wav_data: bytes, client_id: str) -> Tuple[bool, str, dict]:
        """Common transcription logic for both batch and streaming.

        Args:
            wav_data: WAV audio data to transcribe
            client_id: Client identifier for logging

        Returns:
            (success, transcribed_text, info_dict)

        """
        # Validate audio size before processing
        MIN_AUDIO_SIZE = 1000  # Minimum bytes for valid audio (excludes header-only files)
        if len(wav_data) < MIN_AUDIO_SIZE:
            logger.warning(f"Client {client_id}: Audio too small ({len(wav_data)} bytes < {MIN_AUDIO_SIZE}), skipping")
            return False, "", {"error": "Audio data too small"}

        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(wav_data)
            temp_path = temp_file.name

        try:
            # Transcribe in executor to avoid blocking
            logger.info(f"Client {client_id}: Starting transcription...")
            loop = asyncio.get_event_loop()

            def transcribe_audio():
                if not self.backend.is_ready:
                    raise RuntimeError("Backend not ready/model not loaded")
                # Delegate to backend
                return self.backend.transcribe(temp_path, language="en")

            # Serialize GPU work for Parakeet to prevent MPS crashes
            # Acquire semaphore before transcription (queues requests when limit reached)
            if self.transcription_semaphore:
                async with self.transcription_semaphore:
                    logger.debug(f"Client {client_id}: Acquired transcription lock (serialized GPU work)")
                    text, info = await loop.run_in_executor(None, transcribe_audio)
                    logger.debug(f"Client {client_id}: Released transcription lock")
            else:
                # No serialization needed (faster_whisper/huggingface can run concurrently)
                text, info = await loop.run_in_executor(None, transcribe_audio)

            logger.info(f"Client {client_id}: Raw transcription: '{text}' ({len(text)} chars)")

            # Early detection: Skip formatting if transcription contains <unk> tokens (corrupted output)
            if '<unk>' in text:
                logger.warning(f"Client {client_id}: Transcription contains <unk> tokens (corrupted), skipping formatting")
                text = ""  # Return empty to avoid slow formatting pipeline

            # Apply server-side text formatting
            if text.strip():
                try:
                    formatted_text = format_transcription(text)
                    if formatted_text != text:
                        logger.info(
                            f"Client {client_id}: Formatted text: '{formatted_text[:50]}...' ({len(formatted_text)} chars)"
                        )
                    else:
                        logger.info(f"Client {client_id}: Text processed (no changes): '{formatted_text[:50]}...'")
                    text = formatted_text  # Always use formatted version
                except Exception as e:
                    logger.warning(f"Client {client_id}: Text formatting failed: {e}")
                    # Continue with original text

            return (
                True,
                text,
                {
                    "duration": info.get("duration", 0),
                    "language": info.get("language", "en"),
                },
            )

        except Exception as e:
            logger.exception(f"Client {client_id}: Transcription error: {e}")
            return False, "", {"error": str(e)}
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except OSError:
                logger.warning(f"Failed to delete temp file: {temp_path}")

    async def handle_binary_audio(self, websocket, wav_data: bytes, client_ip: str, client_id: str):
        """Handle binary WAV audio data sent directly by clients.

        This provides a simple protocol for clients that send raw WAV data
        without the JSON wrapper. Used by the Rust client for example.

        Args:
            websocket: The WebSocket connection
            wav_data: Raw WAV audio bytes
            client_ip: Client IP address
            client_id: Client identifier
        """
        logger.info(f"Client {client_id}: Received binary audio data ({len(wav_data)} bytes)")

        # DEBUG: Save received WAV for analysis
        debug_dir = "/tmp/stt-debug"
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        debug_path = f"{debug_dir}/web-{timestamp}-{len(wav_data)}b.wav"
        with open(debug_path, "wb") as f:
            f.write(wav_data)
        logger.info(f"DEBUG: Saved received audio to {debug_path}")

        # Check rate limiting
        if not self.check_rate_limit(client_ip):
            await websocket.send(json.dumps({
                "text": "",
                "is_final": True,
                "error": "Rate limit exceeded. Max 10 requests per minute."
            }))
            return

        # Check if model is loaded
        if not self.backend.is_ready:
            await websocket.send(json.dumps({
                "text": "",
                "is_final": True,
                "error": "Server not ready. Model not loaded."
            }))
            return

        try:
            # Use common transcription logic
            success, text, info = await self.transcribe_audio_from_wav(wav_data, client_id)

            if success:
                # Send simple response format for binary protocol
                await websocket.send(json.dumps({
                    "text": text,
                    "is_final": True
                }))
            else:
                await websocket.send(json.dumps({
                    "text": "",
                    "is_final": True,
                    "error": info.get("error", "Transcription failed")
                }))

        except Exception as e:
            logger.exception(f"Client {client_id}: Binary audio transcription error: {e}")
            await websocket.send(json.dumps({
                "text": "",
                "is_final": True,
                "error": str(e)
            }))

    async def handle_ping(self, websocket, data, client_ip, client_id):
        """Handle ping messages"""
        await websocket.send(json.dumps({"type": "pong", "timestamp": time.time()}))

    async def handle_auth(self, websocket, data, client_ip, client_id):
        """Handle authentication messages"""
        token = data.get("token")
        if token == self.auth_token:
            await websocket.send(json.dumps({"type": "auth_success", "message": "Authentication successful"}))
            logger.info(f"Client {client_id} authenticated successfully")
        else:
            await self.send_error(websocket, "Authentication failed")
            logger.warning(f"Client {client_id} authentication failed")

    async def handle_transcription(self, websocket, data, client_ip, client_id):
        """Handle transcription requests"""
        # Check authentication - JWT or legacy token
        token = data.get("token")
        jwt_payload = self.token_manager.validate_token(token)
        if not jwt_payload and token != self.auth_token:
            await self.send_error(websocket, "Authentication required")
            return

        # Log client info if JWT
        if jwt_payload:
            client_name = jwt_payload.get("client_id", "unknown")
            logger.info(f"Transcription request from JWT client: {client_name}")

        # Check rate limiting
        if not self.check_rate_limit(client_ip):
            await self.send_error(websocket, "Rate limit exceeded. Max 10 requests per minute.")
            return

        # Check if model is loaded
        if not self.backend.is_ready:
            await self.send_error(websocket, "Server not ready. Model not loaded.")
            return

        # Get audio data
        audio_data_b64 = data.get("audio_data")
        if not audio_data_b64:
            await self.send_error(websocket, "No audio_data provided")
            return

        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data_b64)
            logger.info(f"Client {client_id}: Received {len(audio_bytes)} bytes of audio data")

            # Check audio format and handle Opus decoding if needed
            audio_format = data.get("audio_format", "wav")
            metadata = data.get("metadata")

            if audio_format == "opus" and metadata:
                try:
                    decoder = OpusBatchDecoder()
                    wav_bytes = decoder.decode_opus_to_wav(audio_bytes, metadata)
                    logger.info(
                        f"Client {client_id}: Decoded Opus ({len(audio_bytes)} bytes) to WAV ({len(wav_bytes)} bytes)"
                    )
                    audio_bytes = wav_bytes
                except Exception as e:
                    logger.error(f"Client {client_id}: Opus decoding failed: {e}")
                    await self.send_error(websocket, f"Opus decoding failed: {e}")
                    return

            # Use common transcription logic
            success, text, info = await self.transcribe_audio_from_wav(audio_bytes, client_id)

            if success:
                # Send successful response
                await websocket.send(
                    json.dumps(
                        {
                            "type": "transcription_complete",
                            "text": text,
                            "success": True,
                            "audio_duration": info.get("duration", 0),
                            "language": info.get("language", "en"),
                        }
                    )
                )
            else:
                await self.send_error(websocket, f"Transcription failed: {info.get('error', 'Unknown error')}")

        except Exception as e:
            logger.exception(f"Client {client_id}: Transcription error: {e}")
            await self.send_error(websocket, f"Transcription failed: {e!s}")

    async def handle_start_stream(self, websocket, data, client_ip, client_id):
        """Handle start of audio streaming session."""
        # Check authentication - JWT or legacy token
        token = data.get("token")
        jwt_payload = self.token_manager.validate_token(token)
        if not jwt_payload and token != self.auth_token:
            await self.send_error(websocket, "Authentication required")
            return

        # Log client info if JWT
        if jwt_payload:
            client_name = jwt_payload.get("client_id", "unknown")
            logger.info(f"Stream session started by JWT client: {client_name}")

        # Check if model is loaded
        if not self.backend.is_ready:
            await self.send_error(websocket, "Server not ready. Model not loaded.")
            return

        # Create session ID for this stream
        session_id = data.get("session_id", f"{client_id}_{uuid.uuid4().hex[:8]}")

        # Get audio parameters
        sample_rate = data.get("sample_rate", 16000)
        channels = data.get("channels", 1)

        # Create new decoder session (for Opus → PCM)
        self.opus_decoder.create_session(session_id, sample_rate, channels)

        # Check if backend supports real-time streaming transcription
        streaming_enabled = False
        backend_info = {}

        if hasattr(self.backend, "supports_streaming") and self.backend.supports_streaming:
            try:
                # Start backend streaming session
                backend_info = await self.backend.start_streaming(session_id)
                streaming_enabled = True
                self.backend_streaming_sessions.add(session_id)
                logger.info(
                    f"Client {client_id}: Started streaming session {session_id} "
                    f"with real-time transcription (backend={self.backend_name})"
                )
            except Exception as e:
                logger.warning(
                    f"Client {client_id}: Failed to start backend streaming for {session_id}: {e}. "
                    "Falling back to batch mode."
                )
                streaming_enabled = False

        if not streaming_enabled:
            logger.info(f"Client {client_id}: Started streaming session {session_id} (batch mode)")

        # Send acknowledgment with streaming capability info
        await websocket.send(
            json.dumps({
                "type": "stream_started",
                "session_id": session_id,
                "success": True,
                "streaming_enabled": streaming_enabled,  # Real-time partial results available
                "backend": self.backend_name,
                **backend_info,
            })
        )

    async def handle_audio_chunk(self, websocket, data, client_ip, client_id):
        """Handle incoming Opus audio chunk."""
        session_id = data.get("session_id")
        if not session_id:
            await self.send_error(websocket, "No session_id provided")
            return

        # Get decoder for this session
        decoder = self.opus_decoder.get_session(session_id)
        if not decoder:
            await self.send_error(websocket, f"Unknown session: {session_id}")
            return

        # Get Opus data (base64 encoded)
        opus_data_b64 = data.get("audio_data")
        if not opus_data_b64:
            await self.send_error(websocket, "No audio_data provided")
            return

        try:
            # Track chunk count for this session
            if session_id not in self.session_chunk_counts:
                self.session_chunk_counts[session_id] = {"received": 0, "expected": None, "opus_log": []}
            self.session_chunk_counts[session_id]["received"] += 1

            # Decode base64 to bytes
            opus_data = base64.b64decode(opus_data_b64)

            # Guard against empty Opus packets that cause decoder errors
            if not opus_data:
                logger.warning(f"Client {client_id} sent an empty audio chunk. Ignoring.")
                return

            # Log what we received for debugging
            chunk_num = self.session_chunk_counts[session_id]["received"]
            logger.debug(f"Client {client_id}: Received chunk #{chunk_num}, size: {len(opus_data)} bytes")

            # Store chunk info for analysis
            self.session_chunk_counts[session_id]["opus_log"].append(
                {"chunk_num": chunk_num, "size": len(opus_data), "data": opus_data}  # Store actual data for analysis
            )

            # Decode Opus chunk and append to PCM buffer
            # This returns the decoded PCM samples as numpy array
            pcm_samples = decoder.decode_chunk(opus_data)

            # If backend streaming is enabled for this session, process chunk in real-time
            if session_id in self.backend_streaming_sessions:
                try:
                    # Process chunk with backend and get partial result
                    result = await self.backend.process_chunk(session_id, pcm_samples)

                    # Send partial result to client (immediate, no throttling)
                    if result.get("text"):
                        await websocket.send(
                            json.dumps({
                                "type": "partial_result",
                                "session_id": session_id,
                                "text": result["text"],
                                "is_final": False,
                                "tokens": result.get("tokens", {}),
                            })
                        )
                except Exception as e:
                    logger.warning(f"Client {client_id}: Error in streaming transcription: {e}")
                    # Continue accumulating audio even if streaming fails

            # Send acknowledgment (optional, for debugging)
            if data.get("ack_requested"):
                await websocket.send(
                    json.dumps(
                        {
                            "type": "chunk_received",
                            "session_id": session_id,
                            "samples_decoded": len(pcm_samples) if pcm_samples is not None else 0,
                            "total_duration": decoder.get_duration(),
                        }
                    )
                )

        except Exception as e:
            logger.exception(f"Error decoding audio chunk: {e}")
            await self.send_error(websocket, f"Audio chunk processing failed: {e!s}")

    async def handle_end_stream(self, websocket, data, client_ip, client_id):
        """Handle end of streaming session and perform transcription.

        Note: No need to wait for chunks - WebSocket guarantees in-order delivery,
        so if we received the end_stream message, all prior chunks have arrived.
        """
        session_id = data.get("session_id")
        if not session_id:
            await self.send_error(websocket, "No session_id provided")
            return

        # Check rate limiting
        if not self.check_rate_limit(client_ip):
            await self.send_error(websocket, "Rate limit exceeded. Max 10 requests per minute.")
            return

        # Log chunk statistics (no waiting needed - WebSocket ensures order)
        expected_chunks = data.get("expected_chunks")
        if expected_chunks is not None:
            chunk_info = self.session_chunk_counts.get(session_id, {"received": 0})
            received_chunks = chunk_info["received"]

            if received_chunks != expected_chunks:
                logger.warning(
                    f"Client {client_id}: Chunk count mismatch - expected {expected_chunks}, received {received_chunks}"
                )
                # Continue anyway - we have what we have
            else:
                logger.info(f"Client {client_id}: All {received_chunks} chunks received")

        # Clean up chunk tracking
        if session_id in self.session_chunk_counts:
            del self.session_chunk_counts[session_id]

        # Get and remove decoder session
        decoder = self.opus_decoder.remove_session(session_id)
        if not decoder:
            await self.send_error(websocket, f"Unknown session: {session_id}")
            return

        # Check if this session was using backend streaming
        using_backend_streaming = session_id in self.backend_streaming_sessions

        try:
            if using_backend_streaming:
                # Use backend's streaming end method for final transcription
                try:
                    result = await self.backend.end_streaming(session_id)
                    text = result.get("text", "")
                    duration = result.get("duration", decoder.get_duration())
                    language = result.get("language", "en")

                    logger.info(
                        f"Client {client_id}: Stream ended (backend streaming). "
                        f"Duration: {duration:.2f}s, Text: {len(text)} chars"
                    )

                    await websocket.send(
                        json.dumps({
                            "type": "stream_transcription_complete",
                            "session_id": session_id,
                            "text": text,
                            "success": True,
                            "audio_duration": duration,
                            "language": language,
                            "backend": self.backend_name,
                            "streaming_mode": True,
                        })
                    )
                    return

                except Exception as e:
                    logger.warning(
                        f"Client {client_id}: Backend end_streaming failed: {e}. "
                        "Falling back to batch transcription."
                    )
                    # Fall through to batch transcription

                finally:
                    # Always clean up backend streaming session
                    self.backend_streaming_sessions.discard(session_id)

            # Batch mode: Use accumulated audio for transcription
            wav_data = decoder.get_wav_data()
            duration = decoder.get_duration()

            logger.info(f"Client {client_id}: Stream ended (batch mode). Duration: {duration:.2f}s, Size: {len(wav_data)} bytes")

            # Use common transcription logic
            success, text, info = await self.transcribe_audio_from_wav(wav_data, client_id)

            if success:
                # Send successful response with streaming-specific fields
                await websocket.send(
                    json.dumps({
                        "type": "stream_transcription_complete",
                        "session_id": session_id,
                        "text": text,
                        "success": True,
                        "audio_duration": duration,
                        "language": info.get("language", "en"),
                        "backend": self.backend_name,
                        "streaming_mode": False,
                    })
                )
            else:
                await self.send_error(websocket, f"Stream transcription failed: {info.get('error', 'Unknown error')}")

        except Exception as e:
            logger.exception(f"Client {client_id}: Stream transcription error: {e}")
            await self.send_error(websocket, f"Stream transcription failed: {e!s}")

        finally:
            # Ensure backend streaming session is cleaned up
            self.backend_streaming_sessions.discard(session_id)

    async def send_error(self, websocket, message):
        """Send error message to client"""
        try:
            await websocket.send(json.dumps({"type": "error", "message": message, "success": False}))
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError) as e:
            logger.warning(f"WebSocket connection closed while sending error: {e}")
        except Exception as e:
            logger.exception(f"Failed to send error message to client: {e}")

    async def health_handler(self, request):
        """HTTP health check endpoint for service monitoring"""
        return web.json_response({
            "status": "healthy",
            "service": "stt",
            "backend": self.backend_name,
            "model_loaded": self.backend.is_ready if self.backend else False,
            "connected_clients": len(self.connected_clients),
            "timestamp": time.time()
        })

    async def start_health_server(self, host, port):
        """Start HTTP health check server"""
        app = web.Application()
        app.router.add_get("/health", self.health_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        logger.info(f"HTTP health endpoint available at http://{host}:{port}/health")
        return runner

    async def start_server(self, host=None, port=None):
        """Start the WebSocket server"""
        # Use provided host/port or defaults
        server_host = host or self.host
        server_port = port or self.port

        # Load model first
        await self.load_model()

        # Start HTTP health server on port+1 (e.g., 8769 -> 8770 for health)
        # Actually, let's use the same port concept but offset by 100 to avoid conflicts
        # The Rust manager expects health on the same port, so use websocket_port for health too
        # We'll run health server on a separate port (websocket_port - 4) to avoid conflict
        health_port = server_port  # Health on same port - but we need different approach
        # Actually aiohttp and websockets can't share a port easily.
        # Let's use the standard health port pattern: websocket+1000 or a fixed offset
        health_port = server_port + 1  # e.g., 8769 -> 8770 for health
        try:
            self._health_runner = await self.start_health_server(server_host, health_port)
        except Exception as e:
            logger.warning(f"Failed to start health server on port {health_port}: {e}")
            # Try alternative port
            try:
                health_port = server_port + 100
                self._health_runner = await self.start_health_server(server_host, health_port)
            except Exception as e2:
                logger.warning(f"Health server disabled: {e2}")

        protocol = "wss" if self.ssl_enabled else "ws"
        logger.info(f"Starting WebSocket server on {protocol}://{server_host}:{server_port}")
        logger.info(f"Your Ubuntu IP: {server_host} (Mac clients should connect to this IP)")
        logger.info(f"Authentication token: {self.auth_token}")
        logger.info(f"Backend: {self.backend_name}")
        if self.backend_name == "faster_whisper":
            logger.info(f"Model: {config.whisper_model}, Device: {config.whisper_device_auto}, Compute: {config.whisper_compute_type_auto}")
        elif self.backend_name == "parakeet":
            logger.info(f"Model: {config.get('parakeet.model', 'default')}")

        if self.ssl_enabled:
            logger.info(f"SSL enabled - cert: {config.ssl_cert_file}, verify: {config.ssl_verify_mode}")

        # Start WebSocket server with SSL support
        server_kwargs = {
            "ping_interval": 30,  # Send ping every 30 seconds
            "ping_timeout": 10,  # Wait 10 seconds for pong
            "max_size": 10 * 1024 * 1024,  # 10MB limit for large audio files
        }

        # Add SSL context if enabled
        if self.ssl_enabled and self.ssl_context:
            server_kwargs["ssl"] = self.ssl_context

        async with websockets.serve(self.handle_client, server_host, server_port, **server_kwargs):
            logger.info("WebSocket Matilda Server is ready for connections!")
            logger.info(f"Protocol: {protocol.upper()}")
            logger.info(f"Active clients: {len(self.connected_clients)}")

            # Keep server running
            await asyncio.Future()


# Enhanced server with dual-mode support
class EnhancedWebSocketServer(MatildaWebSocketServer):
    """Enhanced WebSocket server with full dual-mode support."""

    def __init__(self):
        super().__init__()
        logger.info("Enhanced WebSocket server initialized with dual-mode support")


# Use enhanced server as default
WebSocketTranscriptionServer = EnhancedWebSocketServer


def main():
    """Main function to start the server"""
    server = MatildaWebSocketServer()

    try:
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.exception(f"Server error: {e}")
        logger.exception(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
