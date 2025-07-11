"""Audio streaming with Opus encoding for WebGPU visualizers."""

import asyncio
import numpy as np
from typing import Set, Optional
import weakref
from aiohttp import web

# Setup standardized logging
try:
    from ..config import get_logger
    from .encoder import OpusEncoder

    logger = get_logger(__name__)
except ImportError:
    # Fallback for standalone usage
    import logging

    logging.basicConfig()
    logger = logging.getLogger(__name__)


class AudioStreamer:
    """Handles Opus encoding and streaming to WebSocket clients."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels

        # Use centralized OpusEncoder for encoding
        self.encoder = OpusEncoder(sample_rate, channels, bitrate=24000)

        # Track active connections
        self.connections: Set[web.WebSocketResponse] = weakref.WeakSet()

    async def add_connection(self, ws: web.WebSocketResponse):
        """Add a new WebSocket connection."""
        self.connections.add(ws)
        logger.info(f"Added visualizer connection. Total: {len(self.connections)}")

    async def remove_connection(self, ws: web.WebSocketResponse):
        """Remove a WebSocket connection."""
        # WeakSet automatically removes dead references
        logger.info(f"Removed visualizer connection. Total: {len(self.connections)}")

    async def stream_audio_chunk(self, audio_chunk: np.ndarray):
        """Encode and stream audio chunk to all connected visualizers."""
        if not self.connections:
            return

        # Use OpusEncoder to encode chunk (handles buffering internally)
        encoded = self.encoder.encode_chunk(audio_chunk)

        # Send encoded data if frame is complete
        if encoded:
            await self._send_encoded_frame(encoded)

    async def flush_encoder(self):
        """Flush any remaining audio data in the encoder."""
        if not self.connections:
            return

        # Get final encoded frame
        encoded = self.encoder.flush()
        if encoded:
            await self._send_encoded_frame(encoded)

    async def _send_encoded_frame(self, encoded_data: bytes):
        """Send encoded frame data to all connections."""
        try:
            # Send to all connections concurrently
            tasks = []
            for ws in list(self.connections):  # Copy to avoid modification during iteration
                if not ws.closed:
                    tasks.append(ws.send_bytes(encoded_data))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            logger.error(f"Error streaming audio: {e}")

    def get_stats(self) -> dict:
        """Get streaming statistics."""
        return {
            "active_connections": len(self.connections),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bitrate": self.encoder.bitrate,
            "frame_size": self.encoder.frame_size,
            "buffer_size": self.encoder.buffer_size,
        }


# Global instance
_streamer: Optional[AudioStreamer] = None


def get_audio_streamer() -> AudioStreamer:
    """Get or create the global audio streamer."""
    global _streamer
    if _streamer is None:
        _streamer = AudioStreamer()
    return _streamer
