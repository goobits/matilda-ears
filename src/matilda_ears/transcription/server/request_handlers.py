import base64
import json
import time
from typing import TYPE_CHECKING

from ...audio.opus_batch import OpusBatchDecoder
from ...core.config import setup_logging
from .transcription import send_error, transcribe_audio_from_wav

if TYPE_CHECKING:
    from .core import MatildaWebSocketServer

logger = setup_logging(__name__, log_filename="transcription.txt")


def is_local_client(client_ip: str) -> bool:
    return client_ip in {"127.0.0.1", "::1", "localhost"}


async def handle_binary_audio(
    server: "MatildaWebSocketServer",
    websocket,
    wav_data: bytes,
    client_ip: str,
    client_id: str,
) -> None:
    """Handle binary WAV audio data sent directly by clients.

    This provides a simple protocol for clients that send raw WAV data
    without the JSON wrapper. Used by the Rust client for example.

    Args:
        server: The MatildaWebSocketServer instance
        websocket: The WebSocket connection
        wav_data: Raw WAV audio bytes
        client_ip: Client IP address
        client_id: Client identifier

    """
    logger.debug(f"Client {client_id}: Received binary audio ({len(wav_data)} bytes)")

    # Check rate limiting
    if not server.check_rate_limit(client_ip):
        await websocket.send(
            json.dumps({"text": "", "is_final": True, "error": "Rate limit exceeded. Max 10 requests per minute."})
        )
        return

    # Check if model is loaded
    if not server.backend.is_ready:
        await websocket.send(json.dumps({"text": "", "is_final": True, "error": "Server not ready. Model not loaded."}))
        return

    try:
        # Use common transcription logic
        success, text, info = await transcribe_audio_from_wav(server, wav_data, client_id)

        if success:
            # Send simple response format for binary protocol
            await websocket.send(json.dumps({"text": text, "is_final": True}))
        else:
            await websocket.send(
                json.dumps({"text": "", "is_final": True, "error": info.get("error", "Transcription failed")})
            )

    except Exception as e:
        logger.exception(f"Client {client_id}: Binary audio transcription error: {e}")
        await websocket.send(json.dumps({"text": "", "is_final": True, "error": str(e)}))


async def handle_ping(
    server: "MatildaWebSocketServer",
    websocket,
    data: dict,
    client_ip: str,
    client_id: str,
) -> None:
    """Handle ping messages."""
    await websocket.send(json.dumps({"type": "pong", "timestamp": time.time()}))


async def handle_auth(
    server: "MatildaWebSocketServer",
    websocket,
    data: dict,
    client_ip: str,
    client_id: str,
) -> None:
    """Handle authentication messages."""
    token = data.get("token")
    jwt_payload = server.token_manager.validate_token(token)
    if jwt_payload:
        client_name = jwt_payload.get("client_id", "unknown")
        await websocket.send(
            json.dumps({"type": "auth_success", "message": "Authentication successful", "client_id": client_name})
        )
        logger.info(f"Client {client_id} authenticated successfully")
    else:
        await send_error(websocket, "Authentication failed")
        logger.warning(f"Client {client_id} authentication failed")


async def handle_transcription(
    server: "MatildaWebSocketServer",
    websocket,
    data: dict,
    client_ip: str,
    client_id: str,
) -> None:
    """Handle transcription requests."""
    # Check authentication - JWT only (allow local dev without token)
    token = data.get("token")
    jwt_payload = server.token_manager.validate_token(token) if token else None
    if not jwt_payload:
        logger.warning(f"Client {client_id}: Auth failed (token_present={bool(token)})")
        if not is_local_client(client_ip):
            await send_error(websocket, "Authentication required")
            return

    # Log client info if JWT
    if jwt_payload:
        client_name = jwt_payload.get("client_id", "unknown")
        logger.info(f"Transcription request from JWT client: {client_name}")

    # Check rate limiting
    if not server.check_rate_limit(client_ip):
        await send_error(websocket, "Rate limit exceeded. Max 10 requests per minute.")
        return

    # Check if model is loaded
    if not server.backend.is_ready:
        await send_error(websocket, "Server not ready. Model not loaded.")
        return

    # Get audio data
    audio_data_b64 = data.get("audio_data")
    if not audio_data_b64:
        await send_error(websocket, "No audio_data provided")
        return

    try:
        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_data_b64)
        logger.debug(f"Client {client_id}: Received {len(audio_bytes)} bytes of audio data")

        # Check audio format and handle Opus decoding if needed
        audio_format = data.get("audio_format", "wav")
        metadata = data.get("metadata")

        if audio_format == "opus" and metadata:
            try:
                decoder = OpusBatchDecoder()
                wav_bytes = decoder.decode_opus_to_wav(audio_bytes, metadata)
                logger.debug(
                    f"Client {client_id}: Decoded Opus ({len(audio_bytes)} bytes) to WAV ({len(wav_bytes)} bytes)"
                )
                audio_bytes = wav_bytes
            except Exception as e:
                logger.error(f"Client {client_id}: Opus decoding failed: {e}")
                await send_error(websocket, f"Opus decoding failed: {e}")
                return

        # Use common transcription logic
        success, text, info = await transcribe_audio_from_wav(server, audio_bytes, client_id)

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
            await send_error(websocket, f"Transcription failed: {info.get('error', 'Unknown error')}")

    except Exception as e:
        logger.exception(f"Client {client_id}: Transcription error: {e}")
        await send_error(websocket, f"Transcription failed: {e!s}")
