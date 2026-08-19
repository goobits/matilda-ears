"""Transcription logic for WebSocket server.

This module contains the core transcription functionality including:
- transcribe_audio_from_wav: Main transcription entry point
- _pcm_to_wav: PCM to WAV conversion
- send_error: Error response helper
"""

import asyncio
import json
import os
import tempfile
import uuid
from typing import TYPE_CHECKING

import websockets
from matilda_transport import build_envelope

from ....core.config import get_config, setup_logging
from ....core.memory import current_rss_bytes

if TYPE_CHECKING:
    from ..core import MatildaWebSocketServer

logger = setup_logging(__name__, log_filename="transcription.txt")


def _delete_temp_file(temp_path: str) -> None:
    try:
        os.unlink(temp_path)
    except OSError:
        logger.warning(f"Failed to delete temp file: {temp_path}")


def _transcription_timeout_seconds() -> float | None:
    value = get_config().get("transcription.timeout_seconds", 180)
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        timeout = 180.0
    return timeout if timeout > 0 else None


async def transcribe_audio_from_wav(
    server: "MatildaWebSocketServer",
    wav_data: bytes,
    client_id: str,
) -> tuple[bool, str, dict]:
    """Common transcription logic for both batch and streaming.

    Args:
        server: The MatildaWebSocketServer instance
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

    server.transcriptions_started += 1
    server.transcriptions_inflight += 1
    rss_before = current_rss_bytes()
    started = asyncio.get_running_loop().time()

    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_file.write(wav_data)
        temp_path = temp_file.name

    try:
        # Transcribe in executor to avoid blocking
        logger.info(
            "Client %s: Starting transcription (wav=%d bytes, rss=%s)",
            client_id,
            len(wav_data),
            rss_before,
        )
        loop = asyncio.get_event_loop()

        def transcribe_audio():
            backend = server.backend
            if backend is None or not backend.is_ready:
                raise RuntimeError("Backend not ready/model not loaded")
            # Delegate to backend
            return backend.transcribe(temp_path, language="en")

        timeout_seconds = _transcription_timeout_seconds()
        await server.transcription_executor_semaphore.acquire()
        executor_slot_released = False

        def release_executor_slot_when_done(_task):
            nonlocal executor_slot_released
            if not executor_slot_released:
                server.transcription_executor_semaphore.release()
                executor_slot_released = True

        if server.transcription_semaphore:
            await server.transcription_semaphore.acquire()
            logger.debug(f"Client {client_id}: Acquired transcription lock (serialized GPU work)")
            task = loop.run_in_executor(server.transcription_executor, transcribe_audio)
            task.add_done_callback(release_executor_slot_when_done)

            def release_lock_when_done(_task):
                server.transcription_semaphore.release()
                logger.debug(f"Client {client_id}: Released transcription lock")

            task.add_done_callback(release_lock_when_done)
            if timeout_seconds is None:
                transcript = await task
            else:
                done, _ = await asyncio.wait({task}, timeout=timeout_seconds)
                if not done:
                    raise TimeoutError
                transcript = await task
        else:
            # No serialization needed (faster_whisper/huggingface can run concurrently)
            task = loop.run_in_executor(server.transcription_executor, transcribe_audio)
            task.add_done_callback(release_executor_slot_when_done)
            if timeout_seconds is None:
                transcript = await task
            else:
                done, _ = await asyncio.wait({task}, timeout=timeout_seconds)
                if not done:
                    raise TimeoutError
                transcript = await task

        text = transcript.text

        logger.debug(f"Client {client_id}: Raw transcription: '{text}' ({len(text)} chars)")

        # Early detection: Skip formatting if transcription contains <unk> tokens (corrupted output)
        if "<unk>" in text:
            logger.warning(f"Client {client_id}: Transcription contains <unk> tokens (corrupted), skipping formatting")
            text = ""  # Return empty to avoid slow formatting pipeline

        # Apply server-side Ears Tuner formatting
        if text.strip() and get_config().get("ears_tuner.enabled", False):
            formatter_name = get_config().get("ears_tuner.formatter", "noop")
            try:
                from matilda_ears_tuner import FormatterRequest, get_formatter

                formatter = get_formatter(formatter_name)
                # Formatting locale is separate from STT backend language ("en" is common for Whisper).
                formatting_config = get_config().get("ears_tuner.formatting", {})
                formatter_locale = (
                    (formatting_config.get("locale") if isinstance(formatting_config, dict) else None)
                    or get_config().get("ears_tuner.locale", None)
                    or transcript.language
                    or "en"
                )
                filename_formats = get_config().get("ears_tuner.filename_formats", {})
                request_config = {
                    "formatting": formatting_config if isinstance(formatting_config, dict) else {},
                    "ears_tuner": {"filename_formats": filename_formats if isinstance(filename_formats, dict) else {}},
                }
                formatted_text = formatter.format(
                    FormatterRequest(text=text, language=formatter_locale, config=request_config)
                ).text
                if formatted_text != text:
                    logger.debug(
                        f"Client {client_id}: Formatted text: '{formatted_text[:50]}...' ({len(formatted_text)} chars)"
                    )
                else:
                    logger.debug(f"Client {client_id}: Text processed (no changes): '{formatted_text[:50]}...'")
                text = formatted_text
            except ImportError as e:
                logger.warning(f"Client {client_id}: Ears Tuner formatting unavailable: {e}")
            except Exception as e:
                logger.warning(f"Client {client_id}: Ears Tuner formatting failed: {e}")

        server.transcriptions_completed += 1
        rss_after = current_rss_bytes()
        logger.info(
            "Client %s: Transcription complete (duration=%.2fs, text=%d chars, rss_before=%s, rss_after=%s, rss_delta=%s)",
            client_id,
            asyncio.get_running_loop().time() - started,
            len(text),
            rss_before,
            rss_after,
            None if rss_before is None or rss_after is None else rss_after - rss_before,
        )

        return (
            True,
            text,
            {
                "duration": transcript.duration or 0,
                "language": transcript.language or "en",
            },
        )

    except TimeoutError:
        timeout_seconds = _transcription_timeout_seconds() or 0
        server.transcriptions_timed_out += 1
        logger.error(f"Client {client_id}: Transcription timed out after {timeout_seconds:.1f}s")
        return False, "", {"error": f"Transcription timed out after {timeout_seconds:.1f}s"}
    except Exception as e:
        server.transcriptions_failed += 1
        logger.exception(f"Client {client_id}: Transcription error: {e}")
        return False, "", {"error": str(e)}
    finally:
        server.transcriptions_inflight = max(0, server.transcriptions_inflight - 1)
        task = locals().get("task")
        if task is not None and not task.done():
            task.add_done_callback(lambda _task: _delete_temp_file(temp_path))
        else:
            _delete_temp_file(temp_path)


async def send_envelope(websocket, task: str, result: dict | None = None, error: dict | None = None) -> None:
    payload = build_envelope(
        request_id=str(uuid.uuid4()),
        service="ears",
        task=task,
        result=result,
        error=error,
    )
    await websocket.send(json.dumps(payload))


async def send_error(
    websocket,
    message: str,
    code: str = "bad_request",
    retryable: bool = False,
) -> None:
    """Send error message to client.

    Args:
        websocket: The WebSocket connection
        message: Error message to send

    """
    try:
        await send_envelope(websocket, "error", error={"message": message, "code": code, "retryable": retryable})
    except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError) as e:
        logger.warning(f"WebSocket connection closed while sending error: {e}")
    except Exception as e:
        logger.exception(f"Failed to send error message to client: {e}")
