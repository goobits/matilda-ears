#!/usr/bin/env python3
"""Streaming Audio Monitor - Pipe-based real-time audio streaming.

This replaces AudioFileMonitor's file-based approach with direct pipe streaming
from arecord, eliminating filesystem buffering issues entirely.
"""

import time
import threading
import subprocess
import asyncio
from typing import Any
from dataclasses import dataclass

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

    # Create dummy for type annotations
    class _DummyNumpy:
        class ndarray:
            pass

    np = _DummyNumpy()

# Setup standardized logging
try:
    from ...core.config import setup_logging

    logger = setup_logging(__name__, log_filename="audio_capture.txt")

except ImportError:
    # Fallback for standalone usage
    import logging

    logger = logging.getLogger(__name__)


@dataclass
class StreamingStats:
    """Statistics for streaming performance monitoring."""

    chunks_sent: int = 0
    samples_sent: int = 0
    bytes_sent: int = 0
    total_duration: float = 0.0
    start_time: float | None = None

    def update_chunk(self, chunk_size: int, timestamp: float | None = None) -> None:
        """Update statistics with new chunk information."""
        if timestamp is None:
            timestamp = time.time()

        if self.start_time is None:
            self.start_time = timestamp

        self.chunks_sent += 1
        self.samples_sent += chunk_size
        self.bytes_sent += chunk_size * 2  # 16-bit samples
        self.total_duration = timestamp - self.start_time if self.start_time else 0.0


class PipeBasedAudioStreamer:
    """Pipe-based audio streamer that eliminates filesystem buffering issues.

    Instead of arecord > file.wav + monitor file, this uses:
    arecord | python_process (direct pipe streaming)
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue,
        chunk_duration_ms: int = 32,
        sample_rate: int = 16000,
        audio_device: str | None = None,
    ):
        """Initialize pipe-based audio streamer.

        Args:
            loop: asyncio event loop for thread-safe communication
            queue: asyncio.Queue to send audio chunks to
            chunk_duration_ms: Target duration per chunk in milliseconds (32ms = 512 samples at 16kHz for VAD compatibility)
            sample_rate: Audio sample rate
            audio_device: Optional specific audio device to use

        """
        # Store loop and queue, remove the old callback system.
        self.loop = loop
        self.queue = queue
        self.chunk_duration_ms = chunk_duration_ms
        self.sample_rate = sample_rate
        self.audio_device = audio_device

        # Get config for cross-platform audio tools
        try:
            from ..core.config import get_config

            self.config = get_config()
        except ImportError:
            self.config = None

        # Calculate chunk size
        self.target_chunk_size = int(sample_rate * chunk_duration_ms / 1000)
        self.target_bytes_per_chunk = self.target_chunk_size * 2  # 16-bit samples

        # Process management
        self.arecord_process: subprocess.Popen | None = None
        self.reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Statistics
        self.stats = StreamingStats()

        # Buffer for accumulating partial chunks
        self._audio_buffer = b""

        logger.info(
            f"[PIPE-STREAM] Initialized: {chunk_duration_ms}ms chunks, {sample_rate}Hz, "
            f"{self.target_chunk_size} samples/chunk"
        )

    def _build_audio_command(self) -> list[str]:
        """Build platform-specific audio capture command."""
        import platform

        # Get audio tool from config (uses existing get_audio_tool method)
        audio_tool = "arecord"  # Default fallback
        if self.config:
            audio_tool = self.config.get_audio_tool()

        if audio_tool == "ffmpeg":
            # Platform-specific ffmpeg command
            system = platform.system()
            if system == "Darwin":
                # macOS: Use AVFoundation
                cmd = [
                    "ffmpeg",
                    "-f",
                    "avfoundation",
                    "-i",
                    f":{self.audio_device or '0'}",  # :0 = default audio input
                    "-ar",
                    str(self.sample_rate),
                    "-ac",
                    "1",
                    "-f",
                    "s16le",
                    "-",  # Output to stdout
                ]
            elif system == "Windows":
                # Windows: Use DirectShow
                cmd = [
                    "ffmpeg",
                    "-f",
                    "dshow",
                    "-i",
                    f"audio={self.audio_device or 'default'}",
                    "-ar",
                    str(self.sample_rate),
                    "-ac",
                    "1",
                    "-f",
                    "s16le",
                    "-",  # Output to stdout
                ]
            else:
                # Linux: Use ALSA
                cmd = [
                    "ffmpeg",
                    "-f",
                    "alsa",
                    "-i",
                    self.audio_device or "default",
                    "-ar",
                    str(self.sample_rate),
                    "-ac",
                    "1",
                    "-f",
                    "s16le",
                    "-",  # Output to stdout
                ]
        else:
            # Linux/macOS arecord command (existing logic)
            cmd = ["arecord", "-f", "S16_LE", "-r", str(self.sample_rate), "-c", "1", "-t", "raw"]
            if self.audio_device:
                cmd.extend(["-D", self.audio_device])

        return cmd

    def start_recording(self) -> bool:
        """Start recording with direct pipe streaming."""
        try:
            # Build platform-specific audio command
            cmd = self._build_audio_command()

            logger.info(f"[PIPE-STREAM] Starting audio capture: {' '.join(cmd)}")

            # Get audio tool to determine if we should use stdbuf
            audio_tool = "arecord"  # Default fallback
            if self.config:
                audio_tool = self.config.get_audio_tool()

            # Only use stdbuf with arecord (Unix tools), not with ffmpeg
            if audio_tool == "arecord":
                cmd_with_stdbuf = ["stdbuf", "-o0", "-e0"] + cmd
                try:
                    # Try with stdbuf first (to disable arecord's internal buffering)
                    self.arecord_process = subprocess.Popen(
                        cmd_with_stdbuf, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0
                    )
                    logger.info("[PIPE-STREAM] Started with stdbuf for unbuffered output")
                except FileNotFoundError:
                    # Fall back to regular command if stdbuf not available
                    self.arecord_process = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0
                    )
                    logger.info("[PIPE-STREAM] Started without stdbuf")
            else:
                # For ffmpeg and other tools, start directly without stdbuf
                self.arecord_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
                logger.info(f"[PIPE-STREAM] Started {audio_tool} directly")

            # Start reader thread
            self._stop_event.clear()
            self.reader_thread = threading.Thread(target=self._read_pipe_loop, daemon=True)
            self.reader_thread.start()

            logger.info("[PIPE-STREAM] Recording started successfully")
            return True

        except Exception as e:
            logger.info(f"[PIPE-STREAM] Failed to start recording: {e}")
            return False

    def stop_recording(self) -> dict[str, Any]:
        """Stop recording and return final statistics."""
        logger.info("[PIPE-STREAM] Stopping recording...")

        # Signal stop to reader thread
        self._stop_event.set()

        # First terminate arecord to stop new data, but keep the pipe open
        if self.arecord_process and self.arecord_process.poll() is None:
            try:
                logger.info("[PIPE-STREAM] Sending SIGTERM to arecord...")
                self.arecord_process.terminate()
                # Don't wait yet - let reader thread drain the pipe
            except Exception as e:
                logger.error(f"[PIPE-STREAM] Error terminating arecord: {e}")

        # Now wait for reader thread to drain all remaining data
        if self.reader_thread:
            logger.info("[PIPE-STREAM] Waiting for reader thread to drain pipe...")
            self.reader_thread.join(timeout=3.0)  # Give more time for draining
            if self.reader_thread.is_alive():
                logger.warning("[PIPE-STREAM] Reader thread still active - may have hung")

        # Ensure arecord process is fully stopped
        if self.arecord_process:
            try:
                self.arecord_process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                logger.info("[PIPE-STREAM] Force killing arecord process")
                self.arecord_process.kill()
                self.arecord_process.wait()

        # Get final statistics
        final_stats = {
            "chunks_sent": self.stats.chunks_sent,
            "samples_sent": self.stats.samples_sent,
            "bytes_sent": self.stats.bytes_sent,
            "total_duration": self.stats.total_duration,
            "sample_rate": self.sample_rate,
        }

        logger.info(f"[PIPE-STREAM] Recording stopped. Final stats: {final_stats}")
        return final_stats

    def join(self, timeout=None):
        """Wait for the reader thread to finish."""
        if self.reader_thread and self.reader_thread.is_alive():
            logger.info("[PIPE-STREAM] Joining reader thread...")
            self.reader_thread.join(timeout=timeout)
            logger.info("[PIPE-STREAM] Reader thread joined")

        # Process any remaining buffer data
        self._flush_remaining_data()

        # Get final statistics
        final_stats = {
            "chunks_sent": self.stats.chunks_sent,
            "samples_sent": self.stats.samples_sent,
            "bytes_sent": self.stats.bytes_sent,
            "total_duration": self.stats.total_duration,
            "sample_rate": self.sample_rate,
        }

        logger.info(f"[PIPE-STREAM] Recording stopped. Final stats: {final_stats}")
        return final_stats

    def _read_pipe_loop(self):
        """Main loop for reading from arecord pipe."""
        logger.info("[PIPE-STREAM] Reader thread started")

        if self.arecord_process is None or self.arecord_process.stdout is None:
            logger.error("[PIPE-STREAM] No arecord process or stdout available")
            return

        total_bytes_read = 0

        # Make pipe non-blocking to allow better control (Unix only)
        try:
            import fcntl
            import os
            import select

            fd = self.arecord_process.stdout.fileno()
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            use_select = True
        except ImportError:
            # Windows - fcntl/select not available, use blocking reads
            logger.info("[PIPE-STREAM] Using blocking read mode (Windows)")
            use_select = False

        try:
            empty_reads = 0
            while True:
                # Check if we should stop
                if self._stop_event.is_set() and self.arecord_process.poll() is not None:
                    # Process terminated after stop requested
                    # Do a few more reads to ensure we get everything
                    if empty_reads >= 3:
                        logger.info(f"[PIPE-STREAM] Pipe drained after {total_bytes_read} bytes")
                        break

                if use_select:
                    # Unix: Use select with short timeout to avoid blocking forever
                    ready_to_read, _, _ = select.select([self.arecord_process.stdout], [], [], 0.05)

                    if ready_to_read:
                        try:
                            # Read available data (up to 64KB at once)
                            data = self.arecord_process.stdout.read(65536)
                            if data:
                                empty_reads = 0  # Reset counter
                                total_bytes_read += len(data)
                                self._audio_buffer += data
                                self._process_buffered_chunks()
                            else:
                                # Empty read - could be EOF
                                empty_reads += 1
                                if empty_reads >= 3 or self.arecord_process.poll() is not None:
                                    logger.info(f"[PIPE-STREAM] EOF on pipe after {total_bytes_read} bytes")
                                    break
                        except BlockingIOError:
                            # No data available right now
                            empty_reads += 1
                        except Exception as e:
                            logger.error(f"[PIPE-STREAM] Read error: {e}")
                            break
                    else:
                        # No data ready
                        empty_reads += 1
                        if self._stop_event.is_set() or self.arecord_process.poll() is not None:
                            if empty_reads >= 3:
                                logger.info(f"[PIPE-STREAM] No more data after {total_bytes_read} bytes")
                                break
                else:
                    # Windows: Simple blocking read with smaller chunks
                    try:
                        data = self.arecord_process.stdout.read(4096)
                        if data:
                            empty_reads = 0
                            total_bytes_read += len(data)
                            self._audio_buffer += data
                            self._process_buffered_chunks()
                        else:
                            empty_reads += 1
                            if empty_reads >= 3 or self.arecord_process.poll() is not None:
                                logger.info(f"[PIPE-STREAM] EOF on pipe after {total_bytes_read} bytes")
                                break
                    except Exception as e:
                        logger.error(f"[PIPE-STREAM] Read error: {e}")
                        break

        except Exception as e:
            logger.error(f"[PIPE-STREAM] Reader thread error: {e}")

        # Always flush remaining buffer data
        if self._audio_buffer:
            logger.info(f"[PIPE-STREAM] Flushing final {len(self._audio_buffer)} bytes from buffer")
            # Process any remaining chunks
            self._process_buffered_chunks()
            # Then flush partial data
            self._flush_remaining_data()

        logger.info(f"[PIPE-STREAM] Reader thread finished - total {total_bytes_read} bytes read")

    def _process_buffered_chunks(self):
        """Process complete chunks from the buffer."""
        while len(self._audio_buffer) >= self.target_bytes_per_chunk:
            # Extract one chunk
            chunk_bytes = self._audio_buffer[: self.target_bytes_per_chunk]
            self._audio_buffer = self._audio_buffer[self.target_bytes_per_chunk :]

            # Convert to numpy array
            audio_chunk = np.frombuffer(chunk_bytes, dtype=np.int16)

            # Update statistics
            self.stats.update_chunk(len(audio_chunk))

            # Use the thread-safe method to put the item on the async queue.
            try:
                self.loop.call_soon_threadsafe(self.queue.put_nowait, audio_chunk)
            except Exception as e:
                logger.error(f"[PIPE-STREAM] Error putting chunk in queue: {e}")
                # If queue is full or loop is closed, we need to handle this gracefully
                if "Queue is full" in str(e):
                    logger.warning("[PIPE-STREAM] Audio queue is full, dropping chunk to prevent blocking")
                elif "Event loop is closed" in str(e):
                    logger.warning("[PIPE-STREAM] Event loop closed, stopping audio reader")
                    break
                else:
                    # For other errors, re-raise to prevent data corruption
                    raise

    def _flush_remaining_data(self):
        """Flush any remaining partial data in the buffer."""
        if len(self._audio_buffer) >= 2:  # At least one sample
            # Pad to even number of bytes if needed
            if len(self._audio_buffer) % 2 == 1:
                self._audio_buffer += b"\x00"

            # Convert remaining data
            remaining_chunk = np.frombuffer(self._audio_buffer, dtype=np.int16)

            if len(remaining_chunk) > 0:
                self.stats.update_chunk(len(remaining_chunk))
                # Use the same thread-safe method for the final chunk.
                try:
                    self.loop.call_soon_threadsafe(self.queue.put_nowait, remaining_chunk)
                except Exception as e:
                    logger.error(f"[PIPE-STREAM] Final callback error: {e}")

            self._audio_buffer = b""

    def is_recording(self) -> bool:
        """Check if recording is active."""
        return (
            self.arecord_process is not None and self.arecord_process.poll() is None and not self._stop_event.is_set()
        )
