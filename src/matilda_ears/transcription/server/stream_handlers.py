import asyncio
import base64
import os
import time
import uuid
from typing import TYPE_CHECKING

import numpy as np

from ...core.config import get_config, setup_logging
from ...wake_word.detector import WakeWordDetector
from ...audio.conversion import int16_to_float32
from ...audio.decoder import OpusDecoder
from .internal.audio_utils import (
    TARGET_SAMPLE_RATE,
    decode_opus_chunk,
    downmix_to_mono,
    needs_resampling,
    resample_to_16k,
    session_audio_to_wav,
    validate_sample_rate,
)
from .internal.session_registry import PcmBuffer, ServerSession, SessionConflictError, WakeWordState
from .internal.transcription import send_envelope, send_error, transcribe_audio_from_wav


def _create_streaming_session(session_id: str, backend, backend_name: str, transcription_semaphore, vad=None):
    """Create a streaming session using SimulStreaming."""
    from ..streaming import StreamingSession, StreamingConfig

    # Get config from app config
    app_config = get_config()
    streaming_config = app_config.get("streaming", {})
    simul_config = streaming_config.get("simul_streaming", {})
    parakeet_config = streaming_config.get("parakeet", {})

    context_size = parakeet_config.get("context_size", (128, 128))
    if isinstance(context_size, list) and len(context_size) == 2:
        context_size = (int(context_size[0]), int(context_size[1]))
    if not isinstance(context_size, tuple) or len(context_size) != 2:
        context_size = (128, 128)

    config = StreamingConfig(
        backend=str(streaming_config.get("backend", backend_name)).lower(),
        language=simul_config.get("language", "en"),
        model_size=simul_config.get("model_size", "tiny"),  # tiny for CPU streaming
        frame_threshold=simul_config.get("frame_threshold", 25),
        audio_max_len=simul_config.get("audio_max_len", 30.0),
        segment_length=simul_config.get("segment_length", 1.0),
        never_fire=simul_config.get("never_fire", True),
        vad_enabled=bool(simul_config.get("vad_enabled", True)),
        vad_threshold=float(simul_config.get("vad_threshold", 0.5)),
        parakeet_context_size=context_size,
        parakeet_depth=int(parakeet_config.get("depth", 1)),
    )

    return StreamingSession(
        session_id=session_id,
        config=config,
        backend=backend,
        backend_name=backend_name,
        vad=vad,
        inference_semaphore=transcription_semaphore,
    )


if TYPE_CHECKING:
    from .core import MatildaWebSocketServer

logger = setup_logging(__name__, log_filename="transcription.txt")

MAX_PCM_BUFFER_SECONDS = int(os.getenv("MATILDA_EARS_MAX_STREAM_BUFFER_SECONDS", "120"))
MAX_SESSIONS_PER_CLIENT = int(os.getenv("MATILDA_EARS_MAX_SESSIONS_PER_CLIENT", "4"))
MAX_ACTIVE_SESSIONS = int(os.getenv("MATILDA_EARS_MAX_ACTIVE_SESSIONS", "32"))
MAX_DEBUG_OPUS_LOG_CHUNKS = int(os.getenv("MATILDA_EARS_MAX_DEBUG_OPUS_LOG_CHUNKS", "1000"))


def _streaming_enabled() -> bool:
    env_value = os.getenv("STT_STREAMING_ENABLED")
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}

    config = get_config()
    return bool(config.get("streaming", {}).get("enabled", True))


def _append_debug_opus_log(session: ServerSession, entry: dict) -> None:
    session.opus_log.append(entry)
    if len(session.opus_log) > MAX_DEBUG_OPUS_LOG_CHUNKS:
        del session.opus_log[: len(session.opus_log) - MAX_DEBUG_OPUS_LOG_CHUNKS]


def _audio_debug_enabled() -> bool:
    env_value = os.getenv("STT_DEBUG_AUDIO")
    if env_value is None:
        return False
    return env_value.strip().lower() in {"1", "true", "yes", "on"}


def _close_wake_word_state(session: ServerSession, client_id: str) -> None:
    try:
        session.close_wake_word()
    except Exception as exc:
        logger.debug(f"Client {client_id}: Wake word cleanup failed for {session.session_id}: {exc}")


def _log_audio_stats(client_id: str, session_id: str, pcm_samples: np.ndarray) -> None:
    if not _audio_debug_enabled():
        return

    if pcm_samples.size == 0:
        logger.info(f"Client {client_id}: Session {session_id} decoded 0 samples")
        return

    rms = float(np.sqrt(np.mean(pcm_samples.astype(np.float32) ** 2)))
    peak = int(np.max(np.abs(pcm_samples)))
    logger.info(
        f"Client {client_id}: Session {session_id} decoded {pcm_samples.size} samples, rms={rms:.3f}, peak={peak}"
    )


async def _create_wake_word_state(server: "MatildaWebSocketServer", debug_enabled: bool) -> WakeWordState | None:
    if getattr(server, "wake_word_available", None) is False:
        return None
    config = get_config()
    wake_config = config.get("modes", {}).get("wake_word", {})
    try:
        detector = await asyncio.to_thread(WakeWordDetector.from_config, wake_config)
    except Exception as exc:
        logger.warning(f"Wake word detector unavailable: {exc}")
        server.wake_word_available = False
        return None

    server.wake_word_available = True
    return WakeWordState(detector, debug_last_sent=0.0 if debug_enabled else None)


async def _process_wake_word_chunk(
    websocket,
    session: ServerSession,
    pcm_samples: np.ndarray,
) -> None:
    state = session.wake_word
    if state is None:
        return

    detector = state.detector
    max_phrase = None
    max_confidence = 0.0
    detected = None
    for frame in state.frames(pcm_samples):
        detected, phrase, confidence = detector.evaluate(frame)
        if confidence > max_confidence:
            max_confidence = confidence
            max_phrase = phrase
        if detected:
            break

    if detected:
        agent, phrase, confidence = detected
        state.reset()
        await send_envelope(
            websocket,
            "wake_word_detected",
            {
                "type": "wake_word_detected",
                "session_id": session.session_id,
                "agent": agent,
                "phrase": phrase,
                "confidence": confidence,
            },
        )
        return

    if state.debug_last_sent is not None:
        now = time.monotonic()
        if now - state.debug_last_sent >= 0.5:
            state.debug_last_sent = now
            if pcm_samples.size:
                samples = int16_to_float32(pcm_samples)
                rms = float(np.sqrt(np.mean(samples * samples)))
                peak = float(np.max(np.abs(samples)))
            else:
                rms = 0.0
                peak = 0.0
            await send_envelope(
                websocket,
                "wake_word_score",
                {
                    "type": "wake_word_score",
                    "session_id": session.session_id,
                    "phrase": str(max_phrase or ""),
                    "confidence": float(max_confidence),
                    "rms": rms,
                    "peak": peak,
                },
            )


async def _emit_partial_result(
    server: "MatildaWebSocketServer",
    websocket,
    session: ServerSession,
    pcm_samples: np.ndarray,
    client_id: str,
    source: str,
) -> None:
    await _process_wake_word_chunk(websocket, session, pcm_samples)
    if session.streaming is None:
        return

    try:
        result = await session.streaming.process_chunk(pcm_samples)
        if result.confirmed_text or result.tentative_text:
            await send_envelope(
                websocket,
                "partial_result",
                {
                    "type": "partial_result",
                    "session_id": session.session_id,
                    "confirmed_text": result.confirmed_text,
                    "tentative_text": result.tentative_text,
                    "is_final": False,
                },
            )
    except Exception as exc:
        logger.warning(f"Client {client_id}: Error in {source} streaming transcription: {exc}")


async def _process_opus_packet(
    server: "MatildaWebSocketServer",
    websocket,
    session: ServerSession,
    opus_data: bytes,
    client_id: str,
    *,
    ack_requested: bool = False,
    source: str = "Opus",
) -> None:
    if not opus_data:
        logger.warning(f"Client {client_id} sent an empty audio chunk. Ignoring.")
        return

    decoder = session.decoder
    if decoder is None:
        await send_error(websocket, f"Unknown session: {session.session_id}")
        return

    try:
        chunk_num = session.record_chunk()
        logger.debug(f"Client {client_id}: Received {source.lower()} chunk #{chunk_num}, size: {len(opus_data)} bytes")
        if _audio_debug_enabled():
            _append_debug_opus_log(
                session,
                {"chunk_num": chunk_num, "size": len(opus_data), "data": opus_data},
            )

        pcm_samples = decode_opus_chunk(decoder, opus_data)
        _log_audio_stats(client_id, session.session_id, pcm_samples)
        await _emit_partial_result(server, websocket, session, pcm_samples, client_id, source)

        if ack_requested:
            await send_envelope(
                websocket,
                "chunk_received",
                {
                    "type": "chunk_received",
                    "session_id": session.session_id,
                    "samples_decoded": len(pcm_samples),
                    "total_duration": decoder.get_duration(),
                },
            )
    except Exception as exc:
        logger.exception(f"Error processing {source.lower()} audio chunk: {exc}")
        await send_error(
            websocket,
            f"Audio chunk processing failed: {exc!s}",
            code="internal_error",
            retryable=True,
        )


async def handle_start_stream(
    server: "MatildaWebSocketServer",
    websocket,
    data: dict,
    client_ip: str,
    client_id: str,
) -> None:
    """Handle start of audio streaming session."""
    # Check if model is loaded
    if not server.backend.is_ready:
        await send_error(websocket, "Server not ready. Model not loaded.", code="not_ready")
        return

    session_id = str(data.get("session_id") or f"{client_id}_{uuid.uuid4().hex[:8]}")
    if server.sessions.count_for_client(client_id) >= MAX_SESSIONS_PER_CLIENT:
        await send_error(websocket, "Too many active sessions for this client", code="too_many_sessions")
        return

    if len(server.sessions) >= MAX_ACTIVE_SESSIONS:
        await send_error(websocket, "Too many active sessions on server", code="too_many_sessions")
        return

    # Get audio parameters
    sample_rate = data.get("sample_rate", 16000)
    channels = data.get("channels", 1)
    use_binary = bool(data.get("binary"))
    if _audio_debug_enabled():
        logger.info(
            f"Client {client_id}: Start stream {session_id} (rate={sample_rate}, channels={channels}, binary={use_binary})"
        )

    # Validate sample rate
    is_valid, error_msg = validate_sample_rate(sample_rate)
    if not is_valid:
        await send_error(websocket, error_msg)
        return

    # Track if resampling is needed (8kHz -> 16kHz)
    resampling_needed = needs_resampling(sample_rate)
    if resampling_needed:
        logger.debug(
            f"Client {client_id}: Session {session_id} uses {sample_rate}Hz, will resample to {TARGET_SAMPLE_RATE}Hz"
        )

    try:
        session = server.sessions.create(
            session_id,
            client_id,
            "binary" if use_binary else "opus",
            sample_rate=sample_rate,
            channels=channels,
        )
        session.decoder = OpusDecoder(sample_rate, channels)
    except SessionConflictError:
        await send_error(websocket, "Session ID is already active", code="session_conflict")
        return
    except Exception as exc:
        server.sessions.pop(session_id)
        logger.warning(f"Client {client_id}: Failed to initialize decoder for {session_id}: {exc}")
        await send_error(websocket, "Failed to initialize audio decoder", code="decoder_unavailable")
        return

    wake_word_requested = bool(data.get("wake_word_enabled", False))
    wake_word_debug = bool(data.get("wake_word_debug", False))
    if wake_word_requested:
        session.wake_word = await _create_wake_word_state(server, wake_word_debug)
    wake_word_enabled = session.wake_word is not None

    # Try to create streaming session with new framework
    streaming_enabled = False
    strategy_name = None

    if _streaming_enabled():
        try:
            # Create streaming session using SimulStreaming
            streaming_session = _create_streaming_session(
                session_id=session_id,
                backend=server.backend,
                backend_name=server.backend_name,
                transcription_semaphore=server.transcription_semaphore,
            )

            # Start the session
            await streaming_session.start()

            session.streaming = streaming_session
            streaming_enabled = True
            strategy_name = "simul_streaming"

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
    else:
        logger.debug(f"Client {client_id}: Streaming disabled; using batch mode for session {session_id}")

    if not streaming_enabled:
        logger.debug(f"Client {client_id}: Started streaming session {session_id} (batch mode)")

    # Send acknowledgment with streaming capability info
    await send_envelope(
        websocket,
        "stream_started",
        {
            "type": "stream_started",
            "session_id": session_id,
            "success": True,
            "streaming_enabled": streaming_enabled,  # Real-time partial results available
            "backend": server.backend_name,
            "strategy": strategy_name,
            "wake_word_enabled": wake_word_enabled,
        },
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

    session = server.sessions.get_owned(session_id, client_id)
    if session is None:
        await send_error(websocket, f"Unknown session: {session_id}")
        return

    if session.ending:
        logger.debug(f"Client {client_id}: Ignoring Opus chunk for ending session {session_id}")
        return

    decoder = session.decoder
    if not decoder:
        await send_error(websocket, f"Unknown session: {session_id}")
        return

    # Get Opus data (base64 encoded)
    opus_data_b64 = data.get("audio_data")
    if not opus_data_b64:
        await send_error(websocket, "No audio_data provided")
        return

    try:
        opus_data = base64.b64decode(opus_data_b64)
    except (TypeError, ValueError) as exc:
        await send_error(websocket, f"Audio chunk processing failed: {exc!s}")
        return

    await _process_opus_packet(
        server,
        websocket,
        session,
        opus_data,
        client_id,
        ack_requested=bool(data.get("ack_requested")),
    )


async def handle_binary_stream_chunk(
    server: "MatildaWebSocketServer",
    websocket,
    opus_data: bytes,
    client_ip: str,
    client_id: str,
) -> None:
    """Handle incoming Opus audio chunk as binary payload."""
    session = server.sessions.binary_for_client(client_id)
    if session is None:
        await send_error(websocket, "No active binary stream session")
        return
    session_id = session.session_id

    if session.ending:
        logger.debug(f"Client {client_id}: Ignoring Opus chunk for ending session {session_id}")
        return

    decoder = session.decoder
    if not decoder:
        await send_error(websocket, f"Unknown session: {session_id}")
        return

    await _process_opus_packet(server, websocket, session, opus_data, client_id, source="Binary Opus")


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

    session = server.sessions.get(session_id)
    if session is not None and session.client_id != client_id:
        await send_error(websocket, f"Unknown session: {session_id}")
        return
    if session is not None and session.ending:
        logger.debug(f"Client {client_id}: Ignoring chunk for ending session {session_id}")
        return

    if session is None:
        if server.sessions.count_for_client(client_id) >= MAX_SESSIONS_PER_CLIENT:
            await send_error(websocket, "Too many active sessions for this client", code="too_many_sessions")
            return
        if len(server.sessions) >= MAX_ACTIVE_SESSIONS:
            await send_error(websocket, "Too many active sessions on server", code="too_many_sessions")
            return
        sample_rate = data.get("sample_rate", 16000)
        channels = data.get("channels", 1)

        is_valid, error_msg = validate_sample_rate(sample_rate)
        if not is_valid:
            await send_error(websocket, error_msg)
            return
        try:
            session = server.sessions.create(
                session_id,
                client_id,
                "pcm",
                sample_rate=sample_rate,
                channels=channels,
            )
        except SessionConflictError:
            await send_error(websocket, "Session ID is already active", code="session_conflict")
            return

    if session.pcm is None:
        sample_rate = data.get("sample_rate", session.sample_rate)
        channels = data.get("channels", session.channels)
        is_valid, error_msg = validate_sample_rate(sample_rate)
        if not is_valid:
            await send_error(websocket, error_msg)
            return
        session.pcm = PcmBuffer(
            sample_rate=sample_rate,
            channels=channels,
            needs_resampling=needs_resampling(sample_rate),
        )
        if session.pcm.needs_resampling:
            logger.debug(
                f"Client {client_id}: Created PCM session {session_id} ({sample_rate}Hz, {channels}ch) "
                f"- will resample to {TARGET_SAMPLE_RATE}Hz"
            )
        else:
            logger.debug(f"Client {client_id}: Created PCM session {session_id} ({sample_rate}Hz, {channels}ch)")

    pcm_session = session.pcm

    # Get PCM data (base64 encoded)
    pcm_data_b64 = data.get("audio_data")
    if not pcm_data_b64:
        await send_error(websocket, "No audio_data provided")
        return

    try:
        # Decode base64 to bytes
        pcm_bytes = base64.b64decode(pcm_data_b64)
        pcm_session.chunk_count += 1

        # Guard against empty packets
        if not pcm_bytes:
            logger.warning(f"Client {client_id} sent empty PCM chunk. Ignoring.")
            return

        # Convert bytes to numpy int16 array
        pcm_samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        pcm_samples = downmix_to_mono(pcm_samples, pcm_session.channels)

        # Resample to 16kHz if needed (e.g., 8kHz input)
        if pcm_session.needs_resampling:
            pcm_samples = resample_to_16k(pcm_samples, pcm_session.sample_rate)

        # Accumulate samples for batch transcription (if needed)
        # Note: After resampling, samples are at 16kHz
        max_samples = TARGET_SAMPLE_RATE * MAX_PCM_BUFFER_SECONDS
        pcm_session.append(pcm_samples, max_samples)

        # Log periodically
        if pcm_session.chunk_count % 10 == 1:
            output_sample_rate = TARGET_SAMPLE_RATE if pcm_session.needs_resampling else pcm_session.sample_rate
            duration = pcm_session.total_samples / output_sample_rate
            logger.debug(
                f"Client {client_id}: PCM chunk #{pcm_session.chunk_count}, "
                f"size: {len(pcm_bytes)} bytes, total: {duration:.2f}s"
            )

        await _emit_partial_result(server, websocket, session, pcm_samples, client_id, "PCM")

    except Exception as e:
        logger.exception(f"Error processing PCM chunk: {e}")
        await send_error(websocket, f"PCM chunk processing failed: {e!s}", code="internal_error", retryable=True)


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

    session = server.sessions.get_owned(session_id, client_id)
    if session is None:
        await send_error(websocket, f"Unknown session: {session_id}")
        return
    if session.ending:
        return
    session.ending = True

    # Check rate limiting
    if not server.check_rate_limit(client_ip):
        session.ending = False
        await send_error(websocket, "Rate limit exceeded. Max 10 requests per minute.", code="rate_limited")
        return

    # Log chunk statistics (no waiting needed - WebSocket ensures order)
    expected_chunks = data.get("expected_chunks")
    if expected_chunks is not None:
        session.expected_chunks = expected_chunks
        received_chunks = session.chunks_received

        if received_chunks != expected_chunks:
            logger.warning(
                f"Client {client_id}: Chunk count mismatch - expected {expected_chunks}, received {received_chunks}"
            )
            # Continue anyway - we have what we have
        else:
            logger.debug(f"Client {client_id}: All {received_chunks} chunks received")
    elif _audio_debug_enabled():
        logger.info(f"Client {client_id}: Stream ending with {session.chunks_received} chunks")

    session = server.sessions.pop_owned(session_id, client_id)
    if session is None:
        await send_error(websocket, f"Unknown session: {session_id}")
        return
    pcm_session = session.pcm
    decoder = session.decoder
    streaming_session = session.streaming

    if not decoder and not pcm_session and not streaming_session:
        _close_wake_word_state(session, client_id)
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

                if not text.strip():
                    logger.warning(
                        f"Client {client_id}: Streaming finalize produced empty text for {session_id}; "
                        "falling back to batch transcription."
                    )
                    # Fall through to batch transcription using accumulated decoded audio.
                else:
                    await send_envelope(
                        websocket,
                        "stream_transcription_complete",
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
                        },
                    )
                    return

            except Exception as e:
                logger.warning(
                    f"Client {client_id}: Streaming session finalize failed: {e}. Falling back to batch transcription."
                )
                # Fall through to batch transcription

        audio = session_audio_to_wav(session)
        if audio is None:
            await send_error(websocket, "No audio data in session")
            return
        wav_data, duration = audio
        logger.debug(
            f"Client {client_id}: {session.transport.upper()} stream ended (batch mode). "
            f"Duration: {duration:.2f}s, Size: {len(wav_data)} bytes"
        )

        # Use common transcription logic
        success, text, info = await transcribe_audio_from_wav(server, wav_data, client_id)

        if success:
            # Send successful response with streaming-specific fields
            await send_envelope(
                websocket,
                "stream_transcription_complete",
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
                },
            )
        else:
            await send_error(
                websocket,
                f"Stream transcription failed: {info.get('error', 'Unknown error')}",
                code="internal_error",
                retryable=True,
            )

    except Exception as e:
        logger.exception(f"Client {client_id}: Stream transcription error: {e}")
        await send_error(websocket, f"Stream transcription failed: {e!s}", code="internal_error", retryable=True)

    finally:
        _close_wake_word_state(session, client_id)
        session.ending = False
