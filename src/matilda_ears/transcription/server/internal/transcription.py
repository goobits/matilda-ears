"""Transcription logic for WebSocket server.

This module contains the core transcription functionality including:
- transcribe_audio_from_wav: Main transcription entry point
- _pcm_to_wav: PCM to WAV conversion
- send_error: Error response helper
"""

import asyncio
import io
import os
import tempfile
import wave
from typing import TYPE_CHECKING

import numpy as np
import websockets

from ....core.config import get_config, setup_logging

if TYPE_CHECKING:
    from .core import MatildaWebSocketServer

logger = setup_logging(__name__, log_filename="transcription.txt")


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

    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_file.write(wav_data)
        temp_path = temp_file.name

    try:
        # Transcribe in executor to avoid blocking
        logger.debug(f"Client {client_id}: Starting transcription...")
        loop = asyncio.get_event_loop()

        def transcribe_audio():
            if not server.backend.is_ready:
                raise RuntimeError("Backend not ready/model not loaded")
            # Delegate to backend
            return server.backend.transcribe(temp_path, language="en")

        # Serialize GPU work for Parakeet to prevent MPS crashes
        # Acquire semaphore before transcription (queues requests when limit reached)
        if server.transcription_semaphore:
            async with server.transcription_semaphore:
                logger.debug(f"Client {client_id}: Acquired transcription lock (serialized GPU work)")
                text, info = await loop.run_in_executor(None, transcribe_audio)
                logger.debug(f"Client {client_id}: Released transcription lock")
        else:
            # No serialization needed (faster_whisper/huggingface can run concurrently)
            text, info = await loop.run_in_executor(None, transcribe_audio)

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
                formatted_text = formatter.format(FormatterRequest(text=text, language=info.get("language", "en"))).text
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


def pcm_to_wav(samples: np.ndarray, sample_rate: int, channels: int = 1) -> bytes:
    """Convert PCM samples to WAV format.

    Args:
        samples: Int16 PCM samples as numpy array
        sample_rate: Sample rate in Hz
        channels: Number of channels (1 for mono)

    Returns:
        WAV file data as bytes

    """
    # Ensure samples are int16
    if samples.dtype != np.int16:
        samples = samples.astype(np.int16)

    # Create WAV in memory
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit = 2 bytes
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(samples.tobytes())

    return buffer.getvalue()


async def send_error(websocket, message: str) -> None:
    """Send error message to client.

    Args:
        websocket: The WebSocket connection
        message: Error message to send

    """
    import json

    try:
        await websocket.send(json.dumps({"type": "error", "message": message, "success": False}))
    except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError) as e:
        logger.warning(f"WebSocket connection closed while sending error: {e}")
    except Exception as e:
        logger.exception(f"Failed to send error message to client: {e}")
