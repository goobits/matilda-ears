#!/usr/bin/env python3
"""Stream Handler for STT Hotkey Daemon

This module provides a self-contained handler for the complex real-time audio streaming
pipeline. It isolates all streaming logic from the main daemon, managing the complete
lifecycle of a streaming session including audio capture, websocket communication,
and graceful shutdown.

Design Benefits:
- Isolates complex, multi-threaded streaming logic from main daemon
- Self-contained streaming session management
- Clean async interface for daemon integration
- Robust error handling and resource cleanup
- Clear separation between streaming and batch transcription
"""

import asyncio
import uuid
from typing import Optional, Dict, Any
from dataclasses import dataclass

from ..core.config import get_config, setup_logging
from .client import StreamingAudioClient
from ..audio.capture import PipeBasedAudioStreamer

# Setup logging and config
logger = setup_logging(__name__, log_filename="transcription.txt")
config = get_config()


@dataclass
class StreamingResult:
    """Result of a streaming session."""

    success: bool
    transcription_text: Optional[str] = None
    error_message: Optional[str] = None
    session_id: Optional[str] = None
    chunks_processed: int = 0
    final_stats: Optional[Dict[str, Any]] = None


class StreamHandler:
    """Self-contained handler for real-time audio streaming sessions.

    This class manages the complete lifecycle of a streaming session:
    1. Creates and configures streaming client and audio streamer
    2. Manages the async chunk processing pipeline
    3. Handles graceful shutdown with sentinel-based coordination
    4. Cleans up all resources on completion or error
    """

    def __init__(self, key_name: str, websocket_url: str, auth_token: str, visualizer_orchestrator=None):
        """Initialize stream handler for a specific hotkey.

        Args:
            key_name: The hotkey name for this streaming session
            websocket_url: WebSocket URL for transcription server
            auth_token: Authentication token for the server
            visualizer_orchestrator: Optional visualizer orchestrator for audio streaming

        """
        self.key_name = key_name
        self.websocket_url = websocket_url
        self.auth_token = auth_token
        self.visualizer_orchestrator = visualizer_orchestrator

        # Session state
        self.session_id = str(uuid.uuid4())[:8]
        self.running = False
        self.chunks_processed = 0
        self.ready_event = asyncio.Event()  # Signal when streaming is ready
        self._shutdown_event = asyncio.Event()  # Signal for run_streaming() to exit

        # Streaming components (created during run)
        self.streaming_client: Optional[StreamingAudioClient] = None
        self.audio_streamer: Optional[PipeBasedAudioStreamer] = None
        self.audio_queue: Optional[asyncio.Queue] = None
        self.chunk_processor_task: Optional[asyncio.Task] = None

        logger.info(f"StreamHandler initialized for {key_name} with session {self.session_id}")

    async def run(self) -> StreamingResult:
        """Run the complete streaming session.

        This is the main entry point that manages the entire streaming lifecycle:
        1. Sets up streaming client and audio streamer
        2. Starts real-time audio capture and processing
        3. Handles the streaming session until stopped
        4. Returns the final transcription result

        Returns:
            StreamingResult with transcription text or error information

        """
        try:
            logger.info(f"Starting streaming session for {self.key_name}")

            # Setup streaming components
            if not await self._setup_streaming():
                return StreamingResult(success=False, error_message="Failed to setup streaming components")

            # Start streaming pipeline
            if not await self._start_streaming():
                return StreamingResult(success=False, error_message="Failed to start streaming pipeline")

            self.running = True
            self.ready_event.set()  # Signal that streaming is ready
            logger.info(f"Streaming session active for {self.key_name} - waiting for stop signal")

            # Wait for external stop signal (this would be called by the daemon)
            # In practice, the daemon will call stop_streaming() on this instance
            await self._shutdown_event.wait()

            # This should never be reached in normal operation
            logger.warning(f"Streaming session for {self.key_name} ended without explicit stop")
            return StreamingResult(success=False, error_message="Session ended unexpectedly")

        except Exception as e:
            logger.error(f"Error in streaming session for {self.key_name}: {e}")
            return StreamingResult(success=False, error_message=str(e), session_id=self.session_id)
        finally:
            # Ensure cleanup always happens
            await self._cleanup()

    async def stop_streaming(self) -> StreamingResult:
        """Stop the streaming session and return final transcription using a robust,
        deterministic shutdown sequence.

        This implements the correct shutdown sequence:
        1. Stop audio producer (guarantees no new audio enters pipe)
        2. Wait for producer thread to join (guarantees all audio is in queue)
        3. Send sentinel to consumer (signals end of queue)
        4. Wait for chunk processor to finish (guarantees all chunks sent)
        5. Finalize transcription with server (flushes encoder buffer)

        Returns:
            StreamingResult with final transcription text

        """
        if not self.running:
            logger.warning(f"Stream for {self.key_name} is not running")
            return StreamingResult(success=False, error_message="Stream not running")

        try:
            logger.info(f"Stopping streaming session for {self.key_name} with robust shutdown...")
            self.running = False

            # --- CORRECT SHUTDOWN SEQUENCE ---
            # NO MORE asyncio.sleep() - the join() call handles intelligent draining

            # Step 1: Stop the audio producer (arecord). This prevents new audio from entering the pipe.
            # The reader thread in the streamer will continue to process any data already in the pipe.
            final_stats = {}
            loop = asyncio.get_event_loop()
            if self.audio_streamer:
                logger.info("Stopping pipe-based audio streamer...")
                final_stats = await loop.run_in_executor(None, self.audio_streamer.stop_recording)
                logger.info(f"Audio streamer stop initiated. Final stats: {final_stats}")

                # Step 2: Wait for the producer thread to completely finish.
                # This GUARANTEES that all audio from the pipe has been read and put onto the audio_queue.
                logger.info("Waiting for audio producer thread to join...")
                await loop.run_in_executor(None, self.audio_streamer.join, 2.0)
                logger.info("Audio producer thread has joined. No more chunks will be produced.")

            # Step 3: Now that the producer is finished, send the sentinel to the consumer.
            if self.audio_queue:
                logger.info("Placing sentinel (None) on queue to signal end of stream.")
                # Must await the put call for an asyncio.Queue
                await self.audio_queue.put(None)

            # Step 4: Wait for the chunk processor (consumer) to finish.
            if self.chunk_processor_task:
                logger.info("Waiting for chunk processor task to finish...")
                try:
                    # Use queue.join() for the most robust wait.
                    # It waits until task_done() is called for all items.
                    if self.audio_queue is not None:
                        await asyncio.wait_for(self.audio_queue.join(), timeout=10.0)
                    logger.info("Audio queue joined gracefully.")
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for chunk processor for {self.key_name}. Cancelling.")
                    self.chunk_processor_task.cancel()

            # Step 5: Finalize the stream with the server.
            # The streaming_client will flush its own internal Opus encoder buffer and send the end_stream message.
            transcription_text = None
            if self.streaming_client:
                logger.info("Finalizing stream with server (flushing encoder and sending end message)...")
                result = await self.streaming_client.end_stream()

                if result and result.get("success"):
                    transcription_text = result.get("text", "").strip()
                    logger.info(f"Streaming transcription successful: '{transcription_text}'")
                else:
                    error_msg = result.get("message", "Unknown streaming error") if result else "No result from server"
                    logger.error(f"Streaming transcription failed: {error_msg}")
                    self._shutdown_event.set()  # Allow run() to exit
                    return StreamingResult(
                        success=False,
                        error_message=error_msg,
                        session_id=self.session_id,
                        chunks_processed=self.chunks_processed,
                        final_stats=final_stats,
                    )

            # Step 6: Signal the main run() method to exit now that all work is complete.
            self._shutdown_event.set()

            return StreamingResult(
                success=True,
                transcription_text=transcription_text,
                session_id=self.session_id,
                chunks_processed=self.chunks_processed,
                final_stats=final_stats,
            )

        except Exception as e:
            logger.error(f"Error stopping streaming session for {self.key_name}: {e}", exc_info=True)
            # Also signal shutdown on error to prevent the run() method from hanging
            self._shutdown_event.set()
            return StreamingResult(
                success=False,
                error_message=str(e),
                session_id=self.session_id,
                chunks_processed=self.chunks_processed,
            )

    async def _setup_streaming(self) -> bool:
        """Set up streaming client and audio components.

        Returns:
            True if setup was successful

        """
        try:
            # Get streaming configuration
            transcription_config = getattr(config, "transcription", {})
            streaming_config = transcription_config.get("modes", {}).get("streaming", {})

            chunk_duration_ms = streaming_config.get("chunk_duration_ms", 32)  # VAD compatible
            # min_chunk_size = streaming_config.get("min_chunk_size", 1600)
            # buffer_chunks = streaming_config.get("buffer_chunks", 1)

            # Create streaming transcription client
            # Get debug settings from config
            debug_save_audio = config.get("debug.save_audio", False)
            max_debug_chunks = config.get("debug.max_chunks", 1000)

            self.streaming_client = StreamingAudioClient(
                self.websocket_url,
                self.auth_token,
                debug_save_audio=debug_save_audio,
                max_debug_chunks=max_debug_chunks,
            )
            await self.streaming_client.connect()
            self.session_id = await self.streaming_client.start_stream(self.session_id)

            # Create an asyncio.Queue. The maxsize provides "backpressure"
            self.audio_queue = asyncio.Queue(maxsize=100)

            # Get the running event loop to pass to the streamer
            loop = asyncio.get_running_loop()

            # Create pipe-based audio streamer, passing the loop and queue directly
            self.audio_streamer = PipeBasedAudioStreamer(
                loop=loop, queue=self.audio_queue, chunk_duration_ms=chunk_duration_ms, sample_rate=16000
            )

            logger.info(f"Streaming components setup complete for {self.key_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to setup streaming components for {self.key_name}: {e}")
            await self._cleanup()
            return False

    async def _start_streaming(self) -> bool:
        """Start the streaming pipeline.

        Returns:
            True if streaming started successfully

        """
        try:
            # Start pipe-based audio streaming
            if self.audio_streamer is None or not self.audio_streamer.start_recording():
                logger.error(f"Failed to start pipe-based recording for {self.key_name}")
                return False

            # Start async chunk processing task
            self.chunk_processor_task = asyncio.create_task(self._process_streaming_chunks())

            logger.info(f"Streaming pipeline started for {self.key_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to start streaming pipeline for {self.key_name}: {e}")
            return False

    async def _process_streaming_chunks(self):
        """Process audio chunks from the asyncio.Queue until a sentinel is received."""
        try:
            logger.info(f"Starting chunk processor for {self.key_name}")
            self.chunks_processed = 0

            while True:
                # This is now a proper, efficient async operation
                if self.audio_queue is None:
                    break
                audio_data = await self.audio_queue.get()  # np.ndarray of int16 samples

                if audio_data is None:
                    self.audio_queue.task_done()
                    break

                # Send to visualizer if web engine is active
                if (
                    self.visualizer_orchestrator
                    and hasattr(self.visualizer_orchestrator, "server")
                    and self.visualizer_orchestrator.server
                ):
                    # Asynchronously send the chunk to the visualizer without blocking transcription
                    asyncio.create_task(self.visualizer_orchestrator.server.broadcast_audio_chunk(audio_data))

                # Send to transcription server
                if self.streaming_client is not None:
                    await self.streaming_client.send_audio_chunk(audio_data)
                self.chunks_processed += 1
                if self.audio_queue is not None:
                    self.audio_queue.task_done()  # Signal that this item is processed
        except Exception as e:
            logger.error(f"Error in chunk processor for {self.key_name}: {e}")
        finally:
            logger.info(f"Chunk processor for {self.key_name} has finished")

    async def _cleanup(self):
        """Clean up all streaming resources."""
        try:
            logger.info(f"Cleaning up streaming resources for {self.key_name}")

            # Stop audio streamer
            if self.audio_streamer:
                try:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.audio_streamer.stop_recording)
                except Exception as e:
                    logger.error(f"Error stopping audio streamer: {e}")

            # Cancel chunk processor
            if self.chunk_processor_task and not self.chunk_processor_task.done():
                self.chunk_processor_task.cancel()
                try:
                    await self.chunk_processor_task
                except asyncio.CancelledError:
                    pass

            # Disconnect streaming client
            if self.streaming_client:
                try:
                    await self.streaming_client.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting streaming client: {e}")

            logger.info(f"Cleanup complete for {self.key_name}")

        except Exception as e:
            logger.error(f"Error during cleanup for {self.key_name}: {e}")

    async def wait_for_ready(self, timeout: float = 5.0) -> bool:
        """Wait for the streaming session to be ready.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if ready, False if timeout

        """
        try:
            await asyncio.wait_for(self.ready_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for streaming session {self.key_name} to be ready")
            return False

    def get_session_info(self) -> Dict[str, Any]:
        """Get information about the current streaming session.

        Returns:
            Dictionary with session information

        """
        return {
            "session_id": self.session_id,
            "key_name": self.key_name,
            "running": self.running,
            "chunks_processed": self.chunks_processed,
            "has_streaming_client": self.streaming_client is not None,
            "has_audio_streamer": self.audio_streamer is not None,
            "has_chunk_processor": self.chunk_processor_task is not None,
        }

    def is_healthy(self) -> bool:
        """Check if the streaming session is healthy and actually working.

        Returns:
            True if the session is running and all components are active

        """
        if not self.running:
            return False

        # Check if chunk processor task is still alive
        if self.chunk_processor_task and self.chunk_processor_task.done():
            # Task finished - check if it was cancelled or had an exception
            try:
                self.chunk_processor_task.result()
            except Exception:
                return False

        # Check if streaming client is connected
        if self.streaming_client and hasattr(self.streaming_client, "websocket"):
            websocket = self.streaming_client.websocket
            if not websocket:
                return False
            # Check if websocket is closed (different libraries have different attributes)
            if (hasattr(websocket, "closed") and websocket.closed) or (
                hasattr(websocket, "close_code") and websocket.close_code is not None
            ):
                return False

        return True


# ========================= CONVENIENCE FUNCTIONS =========================


def create_stream_handler(
    key_name: str, websocket_url: str, auth_token: str, visualizer_orchestrator=None
) -> StreamHandler:
    """Create a new stream handler instance.

    Args:
        key_name: The hotkey name for this streaming session
        websocket_url: WebSocket URL for transcription server
        auth_token: Authentication token for the server
        visualizer_orchestrator: Optional visualizer orchestrator for audio streaming

    Returns:
        Initialized StreamHandler instance

    """
    return StreamHandler(key_name, websocket_url, auth_token, visualizer_orchestrator)


async def run_streaming_session(key_name: str, websocket_url: str, auth_token: str) -> StreamingResult:
    """Run a complete streaming session with automatic cleanup.

    This is a convenience function for running a streaming session that handles
    setup, execution, and cleanup automatically.

    Args:
        key_name: The hotkey name for this streaming session
        websocket_url: WebSocket URL for transcription server
        auth_token: Authentication token for the server

    Returns:
        StreamingResult with transcription text or error information

    """
    handler = create_stream_handler(key_name, websocket_url, auth_token)
    try:
        # Start streaming in the background
        asyncio.create_task(handler.run())  # streaming_task not used

        # For this convenience function, we simulate waiting for a stop signal
        # In practice, the daemon would control the stop timing
        await asyncio.sleep(0.1)  # Give it time to start

        # Immediately stop for this example - in real use, daemon controls timing
        result = await handler.stop_streaming()
        return result

    except Exception as e:
        logger.error(f"Error in streaming session for {key_name}: {e}")
        return StreamingResult(success=False, error_message=str(e))
    finally:
        # Ensure cleanup
        await handler._cleanup()
