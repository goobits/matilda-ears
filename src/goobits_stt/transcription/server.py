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
from faster_whisper import WhisperModel  # noqa: E402
from goobits_stt.core.config import get_config, setup_logging  # noqa: E402
from goobits_stt.core.token_manager import TokenManager  # noqa: E402
from goobits_stt.audio.decoder import OpusStreamDecoder  # noqa: E402
from goobits_stt.audio.opus_batch import OpusBatchDecoder  # noqa: E402
from goobits_stt.utils.ssl import create_ssl_context  # noqa: E402
from goobits_stt.text_formatting.formatter import format_transcription  # noqa: E402

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
        self.model = None
        self.device = config.whisper_device_auto
        self.compute_type = config.whisper_compute_type_auto

        # WebSocket-level session tracking (self-contained)
        self.streaming_sessions = {}  # session_id -> session_info

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
        """Load Whisper model asynchronously"""
        try:
            logger.info(f"Loading Faster Whisper {self.model_size} model...")
            # Run in thread to avoid blocking event loop
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None, lambda: WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
            )
            logger.info(f"Faster Whisper {self.model_size} model loaded successfully")
        except Exception as e:
            logger.exception(f"Failed to load Whisper model: {e}")
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
                        "server_ready": self.model is not None,
                    }
                )
            )

            async for message in websocket:
                try:
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
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(wav_data)
            temp_path = temp_file.name

        try:
            # Transcribe in executor to avoid blocking
            logger.info(f"Client {client_id}: Starting transcription...")
            loop = asyncio.get_event_loop()

            def transcribe_audio():
                if self.model is None:
                    raise RuntimeError("Model not loaded")
                segments, info = self.model.transcribe(temp_path, beam_size=5, language="en")
                return "".join([segment.text for segment in segments]).strip(), info

            text, info = await loop.run_in_executor(None, transcribe_audio)
            logger.info(f"Client {client_id}: Raw transcription: '{text}' ({len(text)} chars)")
            logger.info(f"Client {client_id}: FULL_RAW_TEXT: {text}")

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
                    "duration": info.duration if hasattr(info, "duration") else 0,
                    "language": info.language if hasattr(info, "language") else "en",
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
        if not self.model:
            await self.send_error(websocket, "Server not ready. Whisper model not loaded.")
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
        if not self.model:
            await self.send_error(websocket, "Server not ready. Whisper model not loaded.")
            return

        # Create session ID for this stream
        session_id = data.get("session_id", f"{client_id}_{uuid.uuid4().hex[:8]}")

        # Get audio parameters
        sample_rate = data.get("sample_rate", 16000)
        channels = data.get("channels", 1)

        # Create new decoder session
        self.opus_decoder.create_session(session_id, sample_rate, channels)

        logger.info(f"Client {client_id}: Started streaming session {session_id}")

        # Send acknowledgment
        await websocket.send(json.dumps({"type": "stream_started", "session_id": session_id, "success": True}))

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
            logger.info(f"Client {client_id}: Received chunk #{chunk_num}, size: {len(opus_data)} bytes")

            # Store chunk info for analysis
            self.session_chunk_counts[session_id]["opus_log"].append(
                {"chunk_num": chunk_num, "size": len(opus_data), "data": opus_data}  # Store actual data for analysis
            )

            # Decode Opus chunk and append to PCM buffer
            samples_decoded = decoder.decode_chunk(opus_data)

            # Send acknowledgment (optional, for debugging)
            if data.get("ack_requested"):
                await websocket.send(
                    json.dumps(
                        {
                            "type": "chunk_received",
                            "session_id": session_id,
                            "samples_decoded": samples_decoded,
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

        # Save server-received Opus data for debugging BEFORE cleanup
        if session_id in self.session_chunk_counts:
            opus_log = self.session_chunk_counts[session_id]["opus_log"]
            if opus_log:
                # Save all received chunks to a file for comparison
                import time

                timestamp = int(time.time())
                server_opus_path = f"/tmp/server-received-opus-{timestamp}.bin"

                with open(server_opus_path, "wb") as f:
                    for chunk_info in opus_log:
                        f.write(chunk_info["data"])

                logger.info(
                    f"Client {client_id}: Saved {len(opus_log)} server-received chunks to {server_opus_path} ({sum(len(chunk['data']) for chunk in opus_log)} bytes total)"
                )

        # Clean up chunk tracking
        if session_id in self.session_chunk_counts:
            del self.session_chunk_counts[session_id]

        # Get and remove decoder session
        decoder = self.opus_decoder.remove_session(session_id)
        if not decoder:
            await self.send_error(websocket, f"Unknown session: {session_id}")
            return

        try:
            # Get accumulated audio as WAV data
            wav_data = decoder.get_wav_data()
            duration = decoder.get_duration()

            logger.info(f"Client {client_id}: Stream ended. Duration: {duration:.2f}s, Size: {len(wav_data)} bytes")

            # DEBUG: Save the final WAV that will be transcribed
            import time as time_module

            timestamp = int(time_module.time())
            debug_wav_path = f"/tmp/debug-server-final-wav-{timestamp}.wav"
            with open(debug_wav_path, "wb") as f:
                f.write(wav_data)
            logger.info(
                f"DEBUG: Saved final WAV for transcription to {debug_wav_path} ({duration:.2f}s, {len(wav_data)} bytes)"
            )

            # Use common transcription logic
            success, text, info = await self.transcribe_audio_from_wav(wav_data, client_id)

            if success:
                # Send successful response with streaming-specific fields
                await websocket.send(
                    json.dumps(
                        {
                            "type": "stream_transcription_complete",
                            "session_id": session_id,
                            "text": text,
                            "success": True,
                            "audio_duration": duration,  # Use duration from decoder
                            "language": info.get("language", "en"),
                        }
                    )
                )
            else:
                await self.send_error(websocket, f"Stream transcription failed: {info.get('error', 'Unknown error')}")

        except Exception as e:
            logger.exception(f"Client {client_id}: Stream transcription error: {e}")
            await self.send_error(websocket, f"Stream transcription failed: {e!s}")

    async def send_error(self, websocket, message):
        """Send error message to client"""
        try:
            await websocket.send(json.dumps({"type": "error", "message": message, "success": False}))
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError) as e:
            logger.warning(f"WebSocket connection closed while sending error: {e}")
        except Exception as e:
            logger.exception(f"Failed to send error message to client: {e}")

    async def start_server(self, host=None, port=None):
        """Start the WebSocket server"""
        # Use provided host/port or defaults
        server_host = host or self.host
        server_port = port or self.port

        # Load model first
        await self.load_model()

        protocol = "wss" if self.ssl_enabled else "ws"
        logger.info(f"Starting WebSocket server on {protocol}://{server_host}:{server_port}")
        logger.info(f"Your Ubuntu IP: {server_host} (Mac clients should connect to this IP)")
        logger.info(f"Authentication token: {self.auth_token}")
        logger.info(f"Model: {self.model_size}, Device: {self.device}, Compute: {self.compute_type}")

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

        try:
            async with websockets.serve(self.handle_client, server_host, server_port, **server_kwargs):
                logger.info("WebSocket Matilda Server is ready for connections!")
                logger.info(f"Protocol: {protocol.upper()}")
                logger.info(f"Active clients: {len(self.connected_clients)}")

                # Keep server running
                await asyncio.Future()
        except OSError as e:
            if e.errno == 98 or "Address already in use" in str(e):
                logger.error(f"Port {server_port} is already in use. Please choose a different port or stop the service using that port.")
                raise RuntimeError(f"Port {server_port} is already in use") from e
            else:
                logger.error(f"Failed to bind to {server_host}:{server_port}: {e}")
                raise


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
