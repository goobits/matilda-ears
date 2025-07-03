"""Enhanced WebSocket STT Server with Dashboard Integration and End-to-End Encryption"""

import asyncio
import base64
import json
import logging
import os
import tempfile
import time
import uuid
import ssl
from pathlib import Path
from typing import Dict, Optional, Any
import websockets
from websockets.server import WebSocketServerProtocol

# Import the existing transcription functionality
import sys

sys.path.append("/app")

from stt_hotkeys.core.text_formatting.formatter import format_transcription
from docker.src.encryption import EncryptionWebSocketHandler, get_encryption_manager
from docker.src.api import dashboard_api

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None
    print("Warning: faster_whisper not available, transcription will be disabled")

logger = logging.getLogger(__name__)


class EnhancedSTTWebSocketServer:
    """Enhanced WebSocket server with dashboard integration and encryption"""

    def __init__(self, host: str = "0.0.0.0", websocket_port: int = 8769, web_port: int = 8080):
        self.host = host
        self.websocket_port = websocket_port
        self.web_port = web_port

        # Whisper model configuration
        self.model_size = os.getenv("WHISPER_MODEL", "large-v3-turbo")
        self.device = "cuda" if self._check_gpu() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.model = None

        # Client tracking
        self.connected_clients: Dict[str, Dict[str, Any]] = {}
        self.client_websockets: Dict[str, WebSocketServerProtocol] = {}

        # Encryption handler
        self.encryption_handler = EncryptionWebSocketHandler(get_encryption_manager())

        # Rate limiting
        self.rate_limits: Dict[str, list] = {}
        self.max_requests_per_minute = 10

        # SSL setup
        self.ssl_context = self._setup_ssl_context()

        # Message handlers
        self.message_handlers = {
            "ping": self.handle_ping,
            "key_exchange": self.handle_key_exchange,
            "auth": self.handle_auth,
            "transcribe": self.handle_transcribe,
            "start_stream": self.handle_start_stream,
            "audio_chunk": self.handle_audio_chunk,
            "end_stream": self.handle_end_stream,
        }

        logger.info("Enhanced STT WebSocket Server initialized")
        logger.info(f"WebSocket: wss://{self.host}:{self.websocket_port}")
        logger.info(f"Dashboard: https://{self.host}:{self.web_port}")
        logger.info(f"Model: {self.model_size} on {self.device}")

    def _check_gpu(self) -> bool:
        """Check if GPU is available"""
        try:
            import torch

            return torch.cuda.is_available()
        except ImportError:
            return False

    def _setup_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Setup SSL context for secure connections"""
        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

            cert_file = "/app/ssl/cert.pem"
            key_file = "/app/ssl/key.pem"

            # Generate certificates if they don't exist
            if not (Path(cert_file).exists() and Path(key_file).exists()):
                self._generate_ssl_certificates()

            ssl_context.load_cert_chain(cert_file, key_file)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            logger.info("SSL context configured successfully")
            return ssl_context

        except Exception as e:
            logger.error(f"Failed to setup SSL: {e}")
            return None

    def _generate_ssl_certificates(self):
        """Generate self-signed SSL certificates"""
        try:
            import subprocess

            # Create SSL directory
            Path("/app/ssl").mkdir(exist_ok=True)

            # Generate certificate
            cmd = [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:4096",
                "-keyout",
                "/app/ssl/key.pem",
                "-out",
                "/app/ssl/cert.pem",
                "-days",
                "365",
                "-nodes",
                "-subj",
                "/C=US/ST=State/L=City/O=STT/OU=Server/CN=localhost",
            ]

            subprocess.run(cmd, check=True, capture_output=True)
            logger.info("Generated SSL certificates")

        except Exception as e:
            logger.error(f"Failed to generate SSL certificates: {e}")
            raise

    async def load_model(self):
        """Load the Whisper model"""
        if not WhisperModel:
            logger.warning("WhisperModel not available, transcription disabled")
            return

        try:
            logger.info(f"Loading Whisper model: {self.model_size}")

            # Load model in executor to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None, lambda: WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
            )

            logger.info("Whisper model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle WebSocket client connections"""
        client_id = str(uuid.uuid4())
        client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"

        logger.info(f"Client {client_id} connected from {client_ip}")

        # Store client connection
        self.connected_clients[client_id] = {
            "ip": client_ip,
            "connected_at": time.time(),
            "authenticated": False,
            "last_activity": time.time(),
        }
        self.client_websockets[client_id] = websocket

        try:
            async for message in websocket:
                await self.handle_message(websocket, message, client_id, client_ip)

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            # Cleanup
            await self.cleanup_client(client_id)

    async def handle_message(self, websocket: WebSocketServerProtocol, message: str, client_id: str, client_ip: str):
        """Handle incoming WebSocket messages"""
        try:
            # Parse message
            data = json.loads(message)
            message_type = data.get("type")

            # Update last activity
            self.connected_clients[client_id]["last_activity"] = time.time()

            # Try to decrypt message if it's encrypted
            decrypted_data = self.encryption_handler.decrypt_client_message(client_id, data)
            if decrypted_data:
                data = decrypted_data
                message_type = data.get("type")

            logger.debug(f"Client {client_id}: Received message type '{message_type}'")

            # Route to appropriate handler
            if message_type in self.message_handlers:
                await self.message_handlers[message_type](websocket, data, client_id, client_ip)
            else:
                await self.send_error(websocket, client_id, f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            await self.send_error(websocket, client_id, "Invalid JSON message")
        except Exception as e:
            logger.error(f"Error handling message from client {client_id}: {e}")
            await self.send_error(websocket, client_id, f"Message handling failed: {e}")

    async def handle_ping(self, websocket: WebSocketServerProtocol, data: Dict, client_id: str, client_ip: str):
        """Handle ping messages"""
        response = {"type": "pong", "timestamp": time.time()}
        await self.send_response(websocket, client_id, response)

    async def handle_key_exchange(self, websocket: WebSocketServerProtocol, data: Dict, client_id: str, client_ip: str):
        """Handle encryption key exchange"""
        response = self.encryption_handler.handle_key_exchange(client_id, data)
        await self.send_response(websocket, client_id, response)

    async def handle_auth(self, websocket: WebSocketServerProtocol, data: Dict, client_id: str, client_ip: str):
        """Handle authentication"""
        token = data.get("token")
        if not token:
            await self.send_error(websocket, client_id, "No token provided")
            return

        try:
            # Validate token with dashboard API
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://localhost:{self.web_port}/api/validate-token", params={"token": token}
                )

                if response.status_code == 200:
                    payload = response.json()
                    self.connected_clients[client_id]["authenticated"] = True
                    self.connected_clients[client_id]["client_name"] = payload.get("client_name", "Unknown")
                    self.connected_clients[client_id]["token_id"] = payload.get("token_id")

                    # Notify dashboard API of active client
                    dashboard_api.mark_client_active(payload.get("token_id"))

                    await self.send_response(
                        websocket,
                        client_id,
                        {"type": "auth_success", "message": "Authentication successful", "encryption_enabled": True},
                    )

                    logger.info(f"Client {client_id} authenticated as {payload.get('client_name')}")
                else:
                    await self.send_error(websocket, client_id, "Authentication failed")

        except Exception as e:
            logger.error(f"Authentication error for client {client_id}: {e}")
            await self.send_error(websocket, client_id, "Authentication error")

    async def handle_transcribe(self, websocket: WebSocketServerProtocol, data: Dict, client_id: str, client_ip: str):
        """Handle transcription requests"""
        # Check authentication
        if not self.connected_clients[client_id].get("authenticated"):
            await self.send_error(websocket, client_id, "Authentication required")
            return

        # Check rate limiting
        if not self.check_rate_limit(client_ip):
            await self.send_error(websocket, client_id, "Rate limit exceeded")
            return

        # Check if model is loaded
        if not self.model:
            await self.send_error(websocket, client_id, "Server not ready - model not loaded")
            return

        # Get audio data
        audio_data_b64 = data.get("audio_data")
        if not audio_data_b64:
            await self.send_error(websocket, client_id, "No audio data provided")
            return

        try:
            # Decode audio
            audio_bytes = base64.b64decode(audio_data_b64)
            logger.info(f"Client {client_id}: Processing {len(audio_bytes)} bytes of audio")

            # Transcribe audio
            result = await self.transcribe_audio(audio_bytes, client_id)

            # Format response
            response = {
                "type": "transcription_result",
                "text": result["text"],
                "confidence": result.get("confidence", 0.0),
                "language": result.get("language", "en"),
                "processing_time": result.get("processing_time", 0.0),
            }

            await self.send_response(websocket, client_id, response)

        except Exception as e:
            logger.error(f"Transcription failed for client {client_id}: {e}")
            await self.send_error(websocket, client_id, f"Transcription failed: {e}")

    async def handle_start_stream(self, websocket: WebSocketServerProtocol, data: Dict, client_id: str, client_ip: str):
        """Handle streaming transcription start"""
        # Implement streaming logic here
        await self.send_response(websocket, client_id, {"type": "stream_started", "session_id": str(uuid.uuid4())})

    async def handle_audio_chunk(self, websocket: WebSocketServerProtocol, data: Dict, client_id: str, client_ip: str):
        """Handle streaming audio chunks"""
        # Implement streaming audio processing here

    async def handle_end_stream(self, websocket: WebSocketServerProtocol, data: Dict, client_id: str, client_ip: str):
        """Handle streaming transcription end"""
        # Implement streaming finalization here
        await self.send_response(
            websocket, client_id, {"type": "stream_ended", "text": "Streaming transcription complete"}
        )

    async def transcribe_audio(self, audio_bytes: bytes, client_id: str) -> Dict[str, Any]:
        """Transcribe audio using Whisper model"""
        try:
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(audio_bytes)
                temp_path = tmp_file.name

            try:
                start_time = time.time()

                # Transcribe with Whisper
                segments, info = self.model.transcribe(temp_path)

                # Collect transcription text
                text = " ".join([segment.text for segment in segments])
                processing_time = time.time() - start_time

                # Format text
                if text.strip():
                    formatted_text = format_transcription(text)
                    if formatted_text != text:
                        logger.info(f"Client {client_id}: Formatted text applied")
                    text = formatted_text

                return {
                    "text": text,
                    "confidence": getattr(info, "confidence", 0.9),
                    "language": getattr(info, "language", "en"),
                    "processing_time": processing_time,
                }

            finally:
                # Clean up temp file
                os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise

    def check_rate_limit(self, client_ip: str) -> bool:
        """Check if client is within rate limits"""
        now = time.time()
        minute_ago = now - 60

        # Clean old entries
        if client_ip in self.rate_limits:
            self.rate_limits[client_ip] = [
                timestamp for timestamp in self.rate_limits[client_ip] if timestamp > minute_ago
            ]
        else:
            self.rate_limits[client_ip] = []

        # Check limit
        if len(self.rate_limits[client_ip]) >= self.max_requests_per_minute:
            return False

        # Add current request
        self.rate_limits[client_ip].append(now)
        return True

    async def send_response(self, websocket: WebSocketServerProtocol, client_id: str, response: Dict[str, Any]):
        """Send response to client with optional encryption"""
        try:
            # Encrypt response if possible
            encrypted_response = self.encryption_handler.encrypt_response(client_id, response)

            # Send response
            await websocket.send(json.dumps(encrypted_response))

        except Exception as e:
            logger.error(f"Failed to send response to client {client_id}: {e}")

    async def send_error(self, websocket: WebSocketServerProtocol, client_id: str, error_message: str):
        """Send error response to client"""
        error_response = {"type": "error", "message": error_message, "timestamp": time.time()}
        await self.send_response(websocket, client_id, error_response)

    async def cleanup_client(self, client_id: str):
        """Clean up client data"""
        if client_id in self.connected_clients:
            client_info = self.connected_clients[client_id]

            # Mark client as inactive in dashboard
            if client_info.get("token_id"):
                dashboard_api.mark_client_inactive(client_info["token_id"])

            # Clean up encryption data
            self.encryption_handler.cleanup_client(client_id)

            # Remove from tracking
            del self.connected_clients[client_id]

        if client_id in self.client_websockets:
            del self.client_websockets[client_id]

    def get_server_stats(self) -> Dict[str, Any]:
        """Get current server statistics"""
        return {
            "connected_clients": len(self.connected_clients),
            "authenticated_clients": len([c for c in self.connected_clients.values() if c.get("authenticated")]),
            "model_loaded": self.model is not None,
            "model_size": self.model_size,
            "device": self.device,
            "uptime": time.time() - getattr(self, "start_time", time.time()),
        }

    async def start_server(self):
        """Start the WebSocket server"""
        self.start_time = time.time()

        # Load Whisper model
        await self.load_model()

        # Start WebSocket server
        logger.info(f"Starting WebSocket server on {self.host}:{self.websocket_port}")

        async with websockets.serve(
            self.handle_client, self.host, self.websocket_port, ssl=self.ssl_context, ping_interval=30, ping_timeout=10
        ):
            logger.info("WebSocket server started successfully")

            # Keep server running
            await asyncio.Future()  # Run forever


# Server instance
websocket_server = None


def get_websocket_server() -> EnhancedSTTWebSocketServer:
    """Get the global WebSocket server instance"""
    global websocket_server
    if websocket_server is None:
        websocket_server = EnhancedSTTWebSocketServer()
    return websocket_server
