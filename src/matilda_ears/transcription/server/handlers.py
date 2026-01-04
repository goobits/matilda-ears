"""Protocol handlers for WebSocket server.

This module contains all message handlers for the WebSocket protocol:
- handle_binary_audio: Binary WAV audio data handler
- handle_ping: Ping/pong handler
- handle_auth: Authentication handler
- handle_transcription: Transcription request handler
- handle_start_stream: Stream start handler
- handle_audio_chunk: Opus audio chunk handler
- handle_pcm_chunk: Raw PCM audio chunk handler
- handle_end_stream: Stream end handler
"""

import base64
import json
import time
import uuid
from typing import TYPE_CHECKING

import numpy as np

from ...audio.opus_batch import OpusBatchDecoder
from ...core.config import setup_logging
from .transcription import pcm_to_wav, send_error, transcribe_audio_from_wav
from .audio_utils import (
    validate_sample_rate,
    needs_resampling,
    resample_to_16k,
    TARGET_SAMPLE_RATE,
)
from ..streaming import create_streaming_session, StreamingConfig

if TYPE_CHECKING:
    from .core import MatildaWebSocketServer

logger = setup_logging(__name__, log_filename="transcription.txt")


def _is_local_client(client_ip: str) -> bool:
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
    if not jwt_payload and not _is_local_client(client_ip):
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


async def handle_start_stream(
    server: "MatildaWebSocketServer",
    websocket,
    data: dict,
    client_ip: str,
    client_id: str,
) -> None:
    """Handle start of audio streaming session."""
    # Check authentication - JWT only (allow local dev without token)
    token = data.get("token")
    jwt_payload = server.token_manager.validate_token(token) if token else None
    if not jwt_payload and not _is_local_client(client_ip):
        await send_error(websocket, "Authentication required")
        return

    # Log client info if JWT
    if jwt_payload:
        client_name = jwt_payload.get("client_id", "unknown")
        logger.debug(f"Stream session started by JWT client: {client_name}")

    # Check if model is loaded
    if not server.backend.is_ready:
        await send_error(websocket, "Server not ready. Model not loaded.")
        return

    # Create session ID for this stream
    session_id = data.get("session_id", f"{client_id}_{uuid.uuid4().hex[:8]}")

    # Track session for this client (for cleanup on disconnect)
    if client_id not in server.client_sessions:
        server.client_sessions[client_id] = set()
    server.client_sessions[client_id].add(session_id)

    # Get audio parameters
    sample_rate = data.get("sample_rate", 16000)
    channels = data.get("channels", 1)

    # Validate sample rate
    is_valid, error_msg = validate_sample_rate(sample_rate)
    if not is_valid:
        await send_error(websocket, error_msg)
        # Clean up session tracking
        if client_id in server.client_sessions:
            server.client_sessions[client_id].discard(session_id)
        return

    # Track if resampling is needed (8kHz -> 16kHz)
    resampling_needed = needs_resampling(sample_rate)
    if resampling_needed:
        logger.debug(
            f"Client {client_id}: Session {session_id} uses {sample_rate}Hz, "
            f"will resample to {TARGET_SAMPLE_RATE}Hz"
        )

    # Create new decoder session (for Opus -> PCM)
    server.opus_decoder.create_session(session_id, sample_rate, channels)

    # Try to create streaming session with new framework
    streaming_enabled = False
    strategy_name = None

    try:
        # Load streaming config
        streaming_config = StreamingConfig.from_config()

        # Create streaming session
        streaming_session = create_streaming_session(
            session_id=session_id,
            backend=server.backend,
            config=streaming_config,
            transcription_semaphore=server.transcription_semaphore,
        )

        # Start the session
        await streaming_session.start()

        # Store session
        server.streaming_sessions[session_id] = streaming_session
        streaming_enabled = True
        strategy_name = streaming_config.strategy

        logger.debug(
            f"Client {client_id}: Started streaming session {session_id} "
            f"with {strategy_name} strategy (backend={server.backend_name})"
        )

    except Exception as e:
        logger.warning(
            f"Client {client_id}: Failed to start streaming session for {session_id}: {e}. "
            "Falling back to batch mode."
        )
        streaming_enabled = False

    if not streaming_enabled:
        logger.debug(f"Client {client_id}: Started streaming session {session_id} (batch mode)")

    # Send acknowledgment with streaming capability info
    await websocket.send(
        json.dumps(
            {
                "type": "stream_started",
                "session_id": session_id,
                "success": True,
                "streaming_enabled": streaming_enabled,  # Real-time partial results available
                "backend": server.backend_name,
                "strategy": strategy_name,
            }
        )
    )


async def handle_audio_chunk(
    server: "MatildaWebSocketServer",
    websocket,
    data: dict,
    client_ip: str,
    client_id: str,
) -> None:
    """Handle incoming Opus audio chunk."""
    session_id = data.get("session_id")
    if not session_id:
        await send_error(websocket, "No session_id provided")
        return

    # Skip if session is ending (prevents race condition)
    if session_id in server.ending_sessions:
        logger.debug(f"Client {client_id}: Ignoring Opus chunk for ending session {session_id}")
        return

    # Get decoder for this session
    decoder = server.opus_decoder.get_session(session_id)
    if not decoder:
        await send_error(websocket, f"Unknown session: {session_id}")
        return

    # Get Opus data (base64 encoded)
    opus_data_b64 = data.get("audio_data")
    if not opus_data_b64:
        await send_error(websocket, "No audio_data provided")
        return

    try:
        # Track chunk count for this session
        if session_id not in server.session_chunk_counts:
            server.session_chunk_counts[session_id] = {"received": 0, "expected": None, "opus_log": []}
        server.session_chunk_counts[session_id]["received"] += 1

        # Decode base64 to bytes
        opus_data = base64.b64decode(opus_data_b64)

        # Guard against empty Opus packets that cause decoder errors
        if not opus_data:
            logger.warning(f"Client {client_id} sent an empty audio chunk. Ignoring.")
            return

        # Log what we received for debugging
        chunk_num = server.session_chunk_counts[session_id]["received"]
        logger.debug(f"Client {client_id}: Received chunk #{chunk_num}, size: {len(opus_data)} bytes")

        # Store chunk info for analysis
        server.session_chunk_counts[session_id]["opus_log"].append(
            {"chunk_num": chunk_num, "size": len(opus_data), "data": opus_data}  # Store actual data for analysis
        )

        # Decode Opus chunk and append to PCM buffer
        # This returns the decoded PCM samples as numpy array
        pcm_samples = decoder.decode_chunk(opus_data)

        # If streaming session exists, process chunk with new framework
        if session_id in server.streaming_sessions:
            try:
                streaming_session = server.streaming_sessions[session_id]
                result = await streaming_session.process_chunk(pcm_samples)

                # Send partial result with new schema (confirmed + tentative)
                if result.confirmed_text or result.tentative_text:
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "partial_result",
                                "session_id": session_id,
                                "confirmed_text": result.confirmed_text,
                                "tentative_text": result.tentative_text,
                                "is_final": False,
                            }
                        )
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
        await send_error(websocket, f"Audio chunk processing failed: {e!s}")


async def handle_pcm_chunk(
    server: "MatildaWebSocketServer",
    websocket,
    data: dict,
    client_ip: str,
    client_id: str,
) -> None:
    """Handle incoming raw PCM audio chunk (for web clients).

    Unlike audio_chunk (Opus), this accepts raw PCM Int16 data directly.
    This bypasses rate limiting for streaming sessions.
    """
    session_id = data.get("session_id")
    if not session_id:
        await send_error(websocket, "No session_id provided")
        return

    # Skip if session is ending (prevents race condition)
    if session_id in server.ending_sessions:
        logger.debug(f"Client {client_id}: Ignoring chunk for ending session {session_id}")
        return

    # Get or create PCM session
    if session_id not in server.pcm_sessions:
        # Initialize PCM session with default parameters
        sample_rate = data.get("sample_rate", 16000)
        channels = data.get("channels", 1)

        # Validate sample rate for new sessions
        is_valid, error_msg = validate_sample_rate(sample_rate)
        if not is_valid:
            await send_error(websocket, error_msg)
            return

        # Track if resampling is needed
        resampling_needed = needs_resampling(sample_rate)

        server.pcm_sessions[session_id] = {
            "samples": [],
            "sample_rate": sample_rate,
            "channels": channels,
            "chunk_count": 0,
            "needs_resampling": resampling_needed,
        }
        if resampling_needed:
            logger.debug(
                f"Client {client_id}: Created PCM session {session_id} ({sample_rate}Hz, {channels}ch) "
                f"- will resample to {TARGET_SAMPLE_RATE}Hz"
            )
        else:
            logger.debug(f"Client {client_id}: Created PCM session {session_id} ({sample_rate}Hz, {channels}ch)")

    pcm_session = server.pcm_sessions[session_id]

    # Get PCM data (base64 encoded)
    pcm_data_b64 = data.get("audio_data")
    if not pcm_data_b64:
        await send_error(websocket, "No audio_data provided")
        return

    try:
        # Decode base64 to bytes
        pcm_bytes = base64.b64decode(pcm_data_b64)
        pcm_session["chunk_count"] += 1

        # Guard against empty packets
        if not pcm_bytes:
            logger.warning(f"Client {client_id} sent empty PCM chunk. Ignoring.")
            return

        # Convert bytes to numpy int16 array
        pcm_samples = np.frombuffer(pcm_bytes, dtype=np.int16)

        # Resample to 16kHz if needed (e.g., 8kHz input)
        if pcm_session.get("needs_resampling", False):
            pcm_samples = resample_to_16k(pcm_samples, pcm_session["sample_rate"])

        # Accumulate samples for batch transcription (if needed)
        # Note: After resampling, samples are at 16kHz
        pcm_session["samples"].append(pcm_samples)

        # Log periodically
        if pcm_session["chunk_count"] % 10 == 1:
            total_samples = sum(len(s) for s in pcm_session["samples"])
            duration = total_samples / pcm_session["sample_rate"]
            logger.debug(
                f"Client {client_id}: PCM chunk #{pcm_session['chunk_count']}, "
                f"size: {len(pcm_bytes)} bytes, total: {duration:.2f}s"
            )

        # If streaming session exists, process chunk with new framework
        if session_id in server.streaming_sessions:
            try:
                streaming_session = server.streaming_sessions[session_id]
                result = await streaming_session.process_chunk(pcm_samples)

                # Send partial result with new schema (confirmed + tentative)
                if result.confirmed_text or result.tentative_text:
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "partial_result",
                                "session_id": session_id,
                                "confirmed_text": result.confirmed_text,
                                "tentative_text": result.tentative_text,
                                "is_final": False,
                            }
                        )
                    )
            except Exception as e:
                logger.warning(f"Client {client_id}: Error in PCM streaming transcription: {e}")
                # Continue accumulating audio even if streaming fails

    except Exception as e:
        logger.exception(f"Error processing PCM chunk: {e}")
        await send_error(websocket, f"PCM chunk processing failed: {e!s}")


async def handle_end_stream(
    server: "MatildaWebSocketServer",
    websocket,
    data: dict,
    client_ip: str,
    client_id: str,
) -> None:
    """Handle end of streaming session and perform transcription.

    Note: No need to wait for chunks - WebSocket guarantees in-order delivery,
    so if we received the end_stream message, all prior chunks have arrived.
    """
    session_id = data.get("session_id")
    if not session_id:
        await send_error(websocket, "No session_id provided")
        return

    # Mark session as ending FIRST (prevents race condition with incoming chunks)
    server.ending_sessions.add(session_id)

    # Check rate limiting
    if not server.check_rate_limit(client_ip):
        server.ending_sessions.discard(session_id)
        await send_error(websocket, "Rate limit exceeded. Max 10 requests per minute.")
        return

    # Log chunk statistics (no waiting needed - WebSocket ensures order)
    expected_chunks = data.get("expected_chunks")
    if expected_chunks is not None:
        chunk_info = server.session_chunk_counts.get(session_id, {"received": 0})
        received_chunks = chunk_info["received"]

        if received_chunks != expected_chunks:
            logger.warning(
                f"Client {client_id}: Chunk count mismatch - expected {expected_chunks}, received {received_chunks}"
            )
            # Continue anyway - we have what we have
        else:
            logger.debug(f"Client {client_id}: All {received_chunks} chunks received")

    # Clean up chunk tracking
    if session_id in server.session_chunk_counts:
        del server.session_chunk_counts[session_id]

    # Check what type of session this is
    pcm_session = server.pcm_sessions.pop(session_id, None)
    decoder = server.opus_decoder.remove_session(session_id)

    # Get streaming session if it exists
    streaming_session = server.streaming_sessions.pop(session_id, None)

    if not decoder and not pcm_session and not streaming_session:
        await send_error(websocket, f"Unknown session: {session_id}")
        return

    try:
        # If using new streaming framework, finalize the session
        if streaming_session:
            try:
                result = await streaming_session.finalize()
                text = result.confirmed_text
                duration = result.audio_duration_seconds

                logger.debug(
                    f"Client {client_id}: Stream ended (streaming framework). "
                    f"Duration: {duration:.2f}s, Text: {len(text)} chars"
                )

                await websocket.send(
                    json.dumps(
                        {
                            "type": "stream_transcription_complete",
                            "session_id": session_id,
                            "confirmed_text": result.confirmed_text,
                            "tentative_text": "",
                            "success": True,
                            "audio_duration": duration,
                            "language": "en",
                            "backend": server.backend_name,
                            "streaming_mode": True,
                        }
                    )
                )
                return

            except Exception as e:
                logger.warning(
                    f"Client {client_id}: Streaming session finalize failed: {e}. "
                    "Falling back to batch transcription."
                )
                # Fall through to batch transcription

        # Batch mode: Use accumulated audio for transcription
        if pcm_session:
            # PCM session: concatenate accumulated samples and create WAV
            all_samples = (
                np.concatenate(pcm_session["samples"]) if pcm_session["samples"] else np.array([], dtype=np.int16)
            )
            # Use 16kHz if samples were resampled, otherwise original rate
            output_sample_rate = TARGET_SAMPLE_RATE if pcm_session.get("needs_resampling", False) else pcm_session["sample_rate"]
            duration = len(all_samples) / output_sample_rate
            wav_data = pcm_to_wav(all_samples, output_sample_rate, pcm_session["channels"])
            logger.debug(
                f"Client {client_id}: PCM stream ended (batch mode). "
                f"Duration: {duration:.2f}s, Samples: {len(all_samples)}, Size: {len(wav_data)} bytes"
            )
        elif decoder:
            # Opus session: get WAV from decoder
            wav_data = decoder.get_wav_data()
            duration = decoder.get_duration()
            logger.debug(
                f"Client {client_id}: Opus stream ended (batch mode). Duration: {duration:.2f}s, Size: {len(wav_data)} bytes"
            )
        else:
            # No audio data available
            await send_error(websocket, "No audio data in session")
            return

        # Use common transcription logic
        success, text, info = await transcribe_audio_from_wav(server, wav_data, client_id)

        if success:
            # Send successful response with streaming-specific fields
            await websocket.send(
                json.dumps(
                    {
                        "type": "stream_transcription_complete",
                        "session_id": session_id,
                        "confirmed_text": text,
                        "tentative_text": "",
                        "success": True,
                        "audio_duration": duration,
                        "language": info.get("language", "en"),
                        "backend": server.backend_name,
                        "streaming_mode": False,
                    }
                )
            )
        else:
            await send_error(websocket, f"Stream transcription failed: {info.get('error', 'Unknown error')}")

    except Exception as e:
        logger.exception(f"Client {client_id}: Stream transcription error: {e}")
        await send_error(websocket, f"Stream transcription failed: {e!s}")

    finally:
        # Remove from ending sessions (cleanup complete)
        server.ending_sessions.discard(session_id)
        # Remove from client sessions tracking
        if client_id in server.client_sessions:
            server.client_sessions[client_id].discard(session_id)
