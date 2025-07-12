#!/usr/bin/env python3
"""Simple WebSocket server for testing"""
import asyncio
import base64
import json
import logging
import os
import tempfile
import websockets
import ffmpeg
from faster_whisper import WhisperModel

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class SimpleWebSocketServer:
    def __init__(self, host=None, port=None):
        self.host = host or os.getenv("WEBSOCKET_BIND_HOST", "0.0.0.0")
        self.port = int(port or os.getenv("WEBSOCKET_PORT", "8773"))
        self.clients = set()
        self.whisper_model = None

        # Load token manager
        try:
            from docker.src.token_manager import get_token_manager

            self.token_manager = get_token_manager()
            logger.info("Token manager loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load token manager: {e}")
            self.token_manager = None

    def load_whisper_model(self):
        """Load the Whisper model for transcription"""
        if self.whisper_model is not None:
            return

        try:
            model_name = os.getenv("WHISPER_MODEL", "large-v3-turbo")

            # Auto-detect GPU or use CPU based on environment
            gpu_enabled = os.getenv("GPU_ENABLED", "false").lower() == "true"

            if gpu_enabled:
                try:
                    import torch

                    if torch.cuda.is_available():
                        device = "cuda"
                        compute_type = "float16"  # Use float16 for GPU performance
                        logger.info(f"CUDA detected: {torch.cuda.get_device_name(0)}")
                    else:
                        device = "cpu"
                        compute_type = "int8"
                        logger.warning("GPU enabled but CUDA not available, falling back to CPU")
                except ImportError:
                    device = "cpu"
                    compute_type = "int8"
                    logger.warning("PyTorch not available, falling back to CPU")
            else:
                device = "cpu"
                compute_type = "int8"

            logger.info(f"Loading Whisper model: {model_name} on {device} with {compute_type}")

            self.whisper_model = WhisperModel(model_name, device=device, compute_type=compute_type)
            logger.info(f"Whisper model loaded successfully on {device}")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            self.whisper_model = None

    async def transcribe_audio(self, audio_bytes: bytes) -> dict:
        """Transcribe audio using Whisper"""
        if self.whisper_model is None:
            self.load_whisper_model()

        if self.whisper_model is None:
            raise Exception("Whisper model not available")

        # Save audio to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        try:
            # Transcribe with Whisper
            segments, info = self.whisper_model.transcribe(
                temp_path,
                language="en",  # or detect automatically
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            # Combine all segments into full text
            text = " ".join([segment.text.strip() for segment in segments])

            # Calculate average confidence
            confidences = [segment.avg_logprob for segment in segments if hasattr(segment, "avg_logprob")]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.8

            # Convert log probability to confidence percentage (rough approximation)
            confidence = min(1.0, max(0.0, (avg_confidence + 1.0)))

            return {
                "text": text.strip(),
                "confidence": confidence,
                "language": info.language,
                "duration": info.duration,
            }

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    async def validate_token(self, token: str) -> dict:
        """Validate JWT token"""
        if not self.token_manager:
            return None

        try:
            payload = self.token_manager.validate_token(token, mark_as_used=True)
            return payload
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return None

    async def convert_webm_to_wav(self, webm_data: bytes) -> bytes:
        """Convert WebM audio data to WAV format using ffmpeg"""
        try:
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as webm_file:
                webm_file.write(webm_data)
                webm_path = webm_file.name

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_file:
                wav_path = wav_file.name

            try:
                # Use ffmpeg to convert WebM to WAV
                (
                    ffmpeg.input(webm_path)
                    .output(wav_path, format="wav", acodec="pcm_s16le", ar=16000)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )

                # Read the converted WAV data
                with open(wav_path, "rb") as wav_file:
                    wav_data = wav_file.read()

                logger.info(f"Successfully converted WebM ({len(webm_data)} bytes) to WAV ({len(wav_data)} bytes)")
                return wav_data

            finally:
                # Clean up temporary files
                if os.path.exists(webm_path):
                    os.unlink(webm_path)
                if os.path.exists(wav_path):
                    os.unlink(wav_path)

        except Exception as e:
            logger.error(f"Failed to convert WebM to WAV: {e}")
            raise

    async def handle_transcribe_message(self, websocket, data: dict):
        """Handle transcription request with format detection"""
        try:
            audio_format = data.get("format", "wav").lower()
            audio_data = data.get("audio")

            if not audio_data:
                await websocket.send(json.dumps({"type": "error", "message": "No audio data provided"}))
                return

            # Decode base64 audio data
            try:
                audio_bytes = base64.b64decode(audio_data)
            except Exception as e:
                await websocket.send(json.dumps({"type": "error", "message": f"Failed to decode audio data: {e}"}))
                return

            # Convert WebM to WAV if needed
            if audio_format == "webm":
                logger.info(f"Converting WebM audio ({len(audio_bytes)} bytes)")
                try:
                    audio_bytes = await self.convert_webm_to_wav(audio_bytes)
                    logger.info("WebM conversion successful")
                except Exception as e:
                    await websocket.send(json.dumps({"type": "error", "message": f"Failed to convert WebM audio: {e}"}))
                    return
            elif audio_format == "wav":
                logger.info(f"Processing WAV audio ({len(audio_bytes)} bytes)")
            else:
                await websocket.send(
                    json.dumps({"type": "error", "message": f"Unsupported audio format: {audio_format}"})
                )
                return

            # Perform actual transcription with Whisper
            logger.info("Starting Whisper transcription...")
            try:
                result = await self.transcribe_audio(audio_bytes)

                await websocket.send(
                    json.dumps(
                        {
                            "type": "transcription",
                            "text": result["text"],
                            "confidence": result["confidence"],
                            "language": result.get("language", "en"),
                            "duration": result.get("duration", 0),
                            "format_processed": audio_format,
                        }
                    )
                )

                logger.info(f"Transcription completed: '{result['text'][:50]}...'")

            except Exception as e:
                logger.error(f"Whisper transcription failed: {e}")
                await websocket.send(json.dumps({"type": "error", "message": f"Transcription failed: {e}"}))

        except Exception as e:
            logger.error(f"Error in transcribe handler: {e}")
            await websocket.send(json.dumps({"type": "error", "message": f"Transcription failed: {e}"}))
            raise

    async def handle_client(self, websocket):
        """Handle WebSocket client connection"""
        client_id = None

        try:
            # Extract path and token from query parameters
            path = websocket.request.path if hasattr(websocket, "request") else "/ws"
            logger.info(f"WebSocket connection attempt to path: {path}")
            token = None
            if "?" in path:
                params = dict(param.split("=") for param in path.split("?")[1].split("&") if "=" in param)
                token = params.get("token")

            if not token:
                await websocket.send(json.dumps({"type": "error", "message": "No authentication token provided"}))
                return

            # Validate token
            token_data = await self.validate_token(token)
            if not token_data:
                await websocket.send(json.dumps({"type": "error", "message": "Invalid or expired token"}))
                return

            client_id = token_data.get("token_id")
            logger.info(f"Client connected: {token_data.get('client_name')} ({client_id})")

            # Send welcome message
            await websocket.send(
                json.dumps(
                    {
                        "type": "connected",
                        "message": "Connected to Matilda WebSocket server",
                        "client_name": token_data.get("client_name"),
                    }
                )
            )

            self.clients.add(websocket)

            # Handle messages
            async for message in websocket:
                try:
                    data = json.loads(message)

                    if data.get("type") == "transcribe":
                        await self.handle_transcribe_message(websocket, data)
                    else:
                        await websocket.send(
                            json.dumps({"type": "error", "message": f"Unknown message type: {data.get('type')}"})
                        )

                except json.JSONDecodeError:
                    await websocket.send(json.dumps({"type": "error", "message": "Invalid JSON"}))
                except Exception as e:
                    logger.error(f"Error handling message: {e}")
                    await websocket.send(json.dumps({"type": "error", "message": str(e)}))

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Error in client handler: {e}")
        finally:
            if websocket in self.clients:
                self.clients.remove(websocket)

    async def start_server(self):
        """Start the WebSocket server"""
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")

        # Disable SSL for development
        ssl_context = None
        logger.info("Running WebSocket server without SSL for development")

        # Start server with the original handler signature
        async with websockets.serve(self.handle_client, self.host, self.port, ssl=ssl_context):
            logger.info(f"WebSocket server listening on {'wss' if ssl_context else 'ws'}://{self.host}:{self.port}")
            await asyncio.Future()  # run forever


def main():
    """Main entry point"""
    server = SimpleWebSocketServer()
    asyncio.run(server.start_server())


if __name__ == "__main__":
    main()
