#!/usr/bin/env python3
"""
Wake Word Mode - Always-on wake word detection for hands-free activation

This mode provides continuous wake word monitoring with:
- Porcupine integration for "Jarvis" detection
- Seamless transition to conversation mode upon detection
- Low CPU usage for always-on operation
- Exit phrase detection to return to wake word listening
"""

import asyncio
import os
import time
from typing import Dict, Any, Optional, Callable
from pathlib import Path
import sys


from .base_mode import BaseMode

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

try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False


class WakeWordMode(BaseMode):
    """Always-on wake word detection mode with conversation integration."""

    def __init__(self, args, wake_word_callback: Optional[Callable] = None):
        super().__init__(args)
        
        # Load wake word configuration from top-level config
        wake_word_config = self.config.get("wake_word", {})
        
        # Wake word detection settings
        self.access_key = self._get_secure_access_key(wake_word_config)
        self.keyword = wake_word_config.get("keyword", "jarvis")
        self.engine = wake_word_config.get("engine", "porcupine")
        self.confidence_threshold = wake_word_config.get("confidence_threshold", 0.7)
        self.detection_interval_ms = wake_word_config.get("detection_interval_ms", 100)
        self.conversation_timeout_s = wake_word_config.get("conversation_timeout_s", 300)
        self.exit_phrases = wake_word_config.get("exit_phrases", [
            "goodbye jarvis", 
            "stop listening", 
            "sleep jarvis"
        ])
        
        # Wake word model and state
        self.porcupine = None
        self.conversation_mode = None
        self.wake_word_active = True
        self.conversation_active = False
        
        # Audio processing for wake word (smaller chunks for responsiveness)
        self.wake_word_chunk_size = 512   # 32ms at 16kHz for Porcupine
        self.audio_buffer = []
        
        # Callbacks and mode switching
        self.wake_word_callback = wake_word_callback
        self.stop_event = asyncio.Event()
        
        # Check dependencies
        if not PORCUPINE_AVAILABLE:
            raise ImportError(
                "Porcupine is required for WakeWordMode. "
                "Install with: pip install pvporcupine"
            )
        
        if not NUMPY_AVAILABLE:
            raise ImportError(
                "NumPy is required for WakeWordMode. "
                "Install with: pip install numpy"
            )
        
        self.logger.info(f"WakeWordMode initialized - keyword: {self.keyword}, "
                        f"threshold: {self.confidence_threshold}")

    def _get_secure_access_key(self, config: Dict[str, Any]) -> Optional[str]:
        """Get access key from environment variables or config, prioritizing security."""
        
        # 1. Check environment variable first (highest priority)
        access_key = os.getenv("PORCUPINE_ACCESS_KEY")
        if access_key:
            self.logger.info("Using Porcupine access key from environment variable")
            return access_key
        
        # 2. Check .env file in project root
        env_file = Path(__file__).parent.parent.parent / ".env"
        if env_file.exists():
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("PORCUPINE_ACCESS_KEY="):
                            access_key = line.split("=", 1)[1].strip().strip('"\'')
                            if access_key:
                                self.logger.info("Using Porcupine access key from .env file")
                                return access_key
            except Exception as e:
                self.logger.warning(f"Failed to read .env file: {e}")
        
        # 3. Fall back to config file (discouraged for production)
        access_key = config.get("access_key")
        if access_key:
            self.logger.warning("Using Porcupine access key from config.json - consider using environment variables for security")
            return access_key
        
        return None

    async def run(self):
        """Main wake word detection loop."""
        try:
            await self._send_status("starting", "Initializing wake word detection...")
            
            # Load wake word model
            await self._load_wake_word_model()
            
            # Setup audio streaming for wake word detection
            await self._setup_audio_streaming()
            
            # Start the main wake word loop
            await self._wake_word_loop()
            
        except Exception as e:
            self.logger.exception(f"Wake word mode failed: {e}")
            await self._send_error(f"Wake word detection failed: {e}")
        finally:
            await self._cleanup()

    async def _load_wake_word_model(self):
        """Load the Porcupine model asynchronously."""
        try:
            if not self.access_key:
                raise ValueError(
                    "Porcupine access key is required. Set it using one of these methods:\n"
                    "1. Environment variable: export PORCUPINE_ACCESS_KEY='your_key_here'\n"
                    "2. Create .env file: echo 'PORCUPINE_ACCESS_KEY=\"your_key_here\"' > .env\n"
                    "3. Add to config.json (not recommended for production)\n"
                    "Get your free access key at: https://console.picovoice.ai/"
                )

            self.logger.info(f"Loading Porcupine model with keyword: {self.keyword}")

            # Load in executor to avoid blocking
            loop = asyncio.get_event_loop()
            self.porcupine = await loop.run_in_executor(
                None,
                lambda: pvporcupine.create(
                    access_key=self.access_key,
                    keywords=[self.keyword]
                )
            )

            self.logger.info("Porcupine model loaded successfully")
            await self._send_status("ready", f"Wake word detection ready - listening for '{self.keyword}'")

        except Exception as e:
            self.logger.error(f"Failed to load Porcupine model: {e}")
            raise

    async def _setup_audio_streaming(self):
        """Setup audio streaming optimized for wake word detection."""
        # Use smaller buffer and faster chunk processing for wake word responsiveness
        await self._setup_audio_streamer(
            maxsize=50,  # Smaller buffer for wake word
            chunk_duration_ms=32  # 32ms chunks for quick detection
        )
        
        # Start audio recording immediately
        self.audio_streamer.start_recording()
        self.logger.info("Audio streaming started for wake word detection")

    async def _wake_word_loop(self):
        """Continuous wake word monitoring loop."""
        self.logger.info("Starting wake word detection loop")
        
        while not self.stop_event.is_set() and self.wake_word_active:
            try:
                # Get audio chunk with timeout
                chunk = await asyncio.wait_for(
                    self.audio_queue.get(), 
                    timeout=0.1
                )
                
                # Add to buffer for wake word detection
                self.audio_buffer.extend(chunk)
                
                # Process when we have enough audio for wake word detection (32ms)
                if len(self.audio_buffer) >= self.wake_word_chunk_size:
                    await self._process_wake_word_chunk()
                
            except asyncio.TimeoutError:
                # No audio received, continue loop
                continue
            except Exception as e:
                self.logger.warning(f"Wake word processing error: {e}")
                await asyncio.sleep(0.1)  # Brief pause before retry

    async def _process_wake_word_chunk(self):
        """Process audio chunk for wake word detection."""
        try:
            # Extract the required chunk size (512 samples for Porcupine)
            audio_chunk = np.array(self.audio_buffer[:self.wake_word_chunk_size], dtype=np.int16)
            
            # Remove processed chunk from buffer
            self.audio_buffer = self.audio_buffer[self.wake_word_chunk_size:]
            
            # Run wake word detection in executor
            loop = asyncio.get_event_loop()
            keyword_index = await loop.run_in_executor(
                None, lambda: self.porcupine.process(audio_chunk)
            )
            
            # Check for wake word detection
            if keyword_index >= 0:
                self.logger.info(f"🎤 Wake word detected: '{self.keyword}' (index: {keyword_index})")
                await self._handle_wake_word_detected(keyword_index)
            
        except Exception as e:
            self.logger.warning(f"Wake word chunk processing error: {e}")

    async def _handle_wake_word_detected(self, keyword_index: int):
        """Handle wake word detection and transition to conversation mode."""
        try:
            await self._send_status("activated", f"Wake word detected! Activating conversation...", {
                "keyword_index": keyword_index,
                "keyword": self.keyword
            })
            
            # Transition to conversation mode
            await self._activate_conversation_mode()
            
        except Exception as e:
            self.logger.error(f"Failed to handle wake word detection: {e}")
            await self._send_error(f"Wake word activation failed: {e}")

    async def _activate_conversation_mode(self):
        """Activate conversation mode with wake word integration."""
        try:
            # Stop wake word audio streaming
            if self.audio_streamer:
                self.audio_streamer.stop_recording()
            
            # Set state
            self.wake_word_active = False
            self.conversation_active = True
            
            # Import and create conversation mode
            from .conversation import ConversationMode
            
            # Create conversation mode with wake word callback
            conversation_args = self.args
            conversation_args.conversation = True
            
            # Pass the wake word callback to enable built-in exit phrase detection
            self.conversation_mode = ConversationMode(
                conversation_args, 
                wake_word_callback=self._return_to_wake_word_mode
            )
            
            # Start conversation mode
            self.logger.info("🗣️ Conversation mode activated")
            await self.conversation_mode.run()
            
        except Exception as e:
            self.logger.error(f"Failed to activate conversation mode: {e}")
            await self._return_to_wake_word_mode()


    async def _return_to_wake_word_mode(self):
        """Return from conversation mode to wake word listening."""
        try:
            self.logger.info("🔄 Returning to wake word detection mode")
            
            # Cleanup conversation mode
            if self.conversation_mode:
                try:
                    await self.conversation_mode._cleanup()
                except Exception as e:
                    self.logger.warning(f"Conversation cleanup error: {e}")
                finally:
                    self.conversation_mode = None
            
            # Reset state
            self.conversation_active = False
            self.wake_word_active = True
            self.audio_buffer.clear()
            
            # Restart audio streaming for wake word detection
            await self._setup_audio_streaming()
            
            await self._send_status("listening", f"Returned to wake word detection - listening for '{self.keyword}'")
            
            # Continue wake word loop
            await self._wake_word_loop()
            
        except Exception as e:
            self.logger.error(f"Failed to return to wake word mode: {e}")
            await self._send_error(f"Wake word mode restart failed: {e}")

    async def _cleanup(self):
        """Cleanup wake word mode resources."""
        try:
            self.stop_event.set()
            self.wake_word_active = False
            
            # Cleanup Porcupine
            if self.porcupine:
                self.porcupine.delete()
                self.porcupine = None
            
            # Cleanup conversation mode if active
            if self.conversation_mode:
                await self.conversation_mode._cleanup()
            
            # Cleanup audio resources
            if self.audio_streamer:
                self.audio_streamer.stop_recording()
            
            self.logger.info("Wake word mode cleanup completed")
            
        except Exception as e:
            self.logger.warning(f"Wake word cleanup error: {e}")
        
        # Call parent cleanup
        await super()._cleanup()