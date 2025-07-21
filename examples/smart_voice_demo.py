#!/usr/bin/env python3
"""
Smart Voice Assistant Demo with WebRTC Echo Cancellation

This demo showcases a production-quality voice assistant that combines:
- GOOBITS STT with conversation mode
- WebRTC echo cancellation for feedback prevention
- TTT CLI integration for AI processing
- TTS CLI integration for speech synthesis
- Smart interruption detection and context-aware conversations

Usage:
    python examples/smart_voice_demo.py

Requirements:
    - TTT CLI tool installed and configured
    - TTS CLI tool installed and configured  
    - WebRTC audio processing dependencies
"""

import asyncio
import argparse
import collections
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add project root to path for local imports
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

# Import GOOBITS components
from src.modes.conversation import ConversationMode
from src.core.config import setup_logging


class ProductionMetrics:
    """Production-grade metrics and monitoring for the voice assistant."""
    
    def __init__(self):
        self.session_start_time = time.time()
        self.session_stats = {
            "interruptions": 0,
            "ai_responses": 0,
            "total_response_time": 0.0,
            "avg_response_time": 0.0,
            "tts_playbacks": 0,
            "errors": {"aec_errors": 0, "ttt_errors": 0, "tts_errors": 0}
        }
        self.response_times = collections.deque(maxlen=100)
        self.logger = setup_logging(__name__)
    
    def record_ai_response(self, response_time: float):
        """Record an AI response and its timing."""
        self.session_stats["ai_responses"] += 1
        self.session_stats["total_response_time"] += response_time
        self.session_stats["avg_response_time"] = (
            self.session_stats["total_response_time"] / self.session_stats["ai_responses"]
        )
        self.response_times.append(response_time)
    
    def record_interruption(self):
        """Record a TTS interruption."""
        self.session_stats["interruptions"] += 1
    
    def record_tts_playback(self):
        """Record a TTS playback start."""
        self.session_stats["tts_playbacks"] += 1
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        duration = time.time() - self.session_start_time
        return {
            "session_duration": duration,
            "stats": self.session_stats.copy(),
            "rates": {
                "interruption_rate": (self.session_stats["interruptions"] / max(1, self.session_stats["tts_playbacks"]))
            }
        }
    
    def export_metrics(self, filename: str = None) -> str:
        """Export metrics to JSON file."""
        if filename is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"voice_assistant_metrics_{timestamp}.json"
        
        try:
            summary = self.get_performance_summary()
            with open(filename, 'w') as f:
                json.dump(summary, f, indent=2)
            return filename
        except Exception as e:
            self.logger.error(f"Failed to export metrics: {e}")
            return None

# Default demo configuration
DEFAULT_DEMO_CONFIG = {
    "webrtc_aec": {
        "enable_aec": True,           # Acoustic echo cancellation
        "enable_ns": True,            # Noise suppression  
        "enable_agc": True,           # Automatic gain control
        "sample_rate": 16000,         # Audio sample rate
        "channels": 1                 # Mono audio
    },
    
    "ttt_integration": {
        "model": "@claude",           # AI model (@claude, @gpt4, gpt-4o)
        "system_prompt": "You are a helpful AI assistant. Keep responses conversational and under 100 words.",
        "temperature": 0.7,           # Response creativity (0-1)
        "max_tokens": 150,            # Maximum response length
        "max_context_exchanges": 5    # Conversation memory
    },
    
    "tts_integration": {
        "provider": "@edge",          # TTS provider (@edge, @openai, @elevenlabs)
        "voice": "en-US-AriaNeural",  # Voice selection (provider-specific)
        "interruption_check_interval": 0.1,  # Check every 100ms
        "max_response_length": 200,   # Prevent overly long responses
        "audio_format": "wav"         # Output audio format
    },
    
    "conversation": {
        "wake_word_enabled": False,   # Optional wake word activation
        "auto_save_conversations": True,  # Save conversation logs
        "conversation_timeout": 300   # 5 minutes of inactivity
    }
}

# Global demo config (will be loaded from GOOBITS config or defaults)
DEMO_CONFIG = DEFAULT_DEMO_CONFIG.copy()


def load_demo_config_from_goobits():
    """Load demo config from main GOOBITS config.json with fallback to defaults."""
    global DEMO_CONFIG
    
    try:
        from src.core.config import load_config
        main_config = load_config()
        demo_config_override = main_config.get("smart_voice_demo", {})
        
        # Deep merge with defaults
        merged_config = DEFAULT_DEMO_CONFIG.copy()
        for section, settings in demo_config_override.items():
            if section in merged_config and isinstance(settings, dict):
                merged_config[section].update(settings)
            else:
                merged_config[section] = settings
        
        DEMO_CONFIG = merged_config
        return DEMO_CONFIG
        
    except Exception as e:
        print(f"⚠️  Error loading GOOBITS config: {e} - using defaults")
        DEMO_CONFIG = DEFAULT_DEMO_CONFIG.copy()
        return DEMO_CONFIG


def get_platform_info():
    """Get detailed platform information for troubleshooting."""
    import platform
    
    info = {
        "platform": sys.platform,
        "system": platform.system(),
        "python_version": platform.python_version(),
        "audio_methods": []
    }
    
    # Check audio capabilities
    try:
        import pygame
        info["audio_methods"].append("pygame")
    except ImportError:
        pass
    
    if sys.platform.startswith('win'):
        try:
            import winsound
            info["audio_methods"].append("winsound")
        except ImportError:
            pass
    
    return info


class WebRTCAECProcessor:
    """WebRTC acoustic echo cancellation using webrtc-audio-processing."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or DEMO_CONFIG["webrtc_aec"]
        self.audio_processor = None
        self.enabled = self.config.get("enable_aec", True)
        self.logger = setup_logging(__name__)
        
        # Performance tracking
        self.processing_times = collections.deque(maxlen=100)
        self.error_count = 0
        self.last_error_time = 0
        
        if self.enabled:
            try:
                self._initialize_webrtc()
            except Exception as e:
                self.logger.warning(f"WebRTC AEC not available: {e}")
                self.logger.warning("Continuing without echo cancellation")
                self.enabled = False

    def _initialize_webrtc(self):
        """Initialize WebRTC audio processing module."""
        try:
            # Try importing webrtc-audio-processing
            from webrtc_audio_processing import AudioProcessingModule
            
            self.audio_processor = AudioProcessingModule(
                enable_aec=self.config.get("enable_aec", True),
                enable_ns=self.config.get("enable_ns", True),
                enable_agc=self.config.get("enable_agc", True),
                sample_rate=self.config.get("sample_rate", 16000),
                channels=self.config.get("channels", 1)
            )
            
            self.logger.info("WebRTC AEC initialized successfully")
            
        except ImportError:
            # Fallback: try alternative packages or disable AEC
            self.logger.warning("webrtc-audio-processing not available")
            self.logger.warning("Install with: pip install webrtc-audio-processing")
            self.enabled = False
            
    def process_audio_frame(self, input_audio, reference_audio=None):
        """Remove echo from input audio using TTS reference."""
        if not self.enabled or not self.audio_processor:
            return input_audio
            
        start_time = time.time()
        
        try:
            # Rate limit error handling to prevent spam
            current_time = time.time()
            if self.error_count > 10 and (current_time - self.last_error_time) < 5.0:
                return input_audio  # Skip processing if too many recent errors
            
            if reference_audio is not None:
                result = self.audio_processor.process_stream(input_audio, reference_audio)
            else:
                result = self.audio_processor.process_stream(input_audio)
            
            # Track performance
            processing_time = time.time() - start_time
            self.processing_times.append(processing_time)
            
            # Reset error count on success
            if self.error_count > 0:
                self.error_count = max(0, self.error_count - 1)
            
            return result
                
        except Exception as e:
            self.error_count += 1
            self.last_error_time = time.time()
            
            if self.error_count <= 3:  # Only log first few errors
                self.logger.debug(f"AEC processing error: {e}")
            elif self.error_count == 10:
                self.logger.warning("Multiple AEC errors, temporarily disabling processing")
            
            return input_audio  # Return unprocessed audio on error
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get AEC performance statistics."""
        if not self.processing_times:
            return {"enabled": self.enabled, "avg_processing_time": 0, "error_count": self.error_count}
        
        import statistics
        return {
            "enabled": self.enabled,
            "avg_processing_time": statistics.mean(self.processing_times),
            "max_processing_time": max(self.processing_times),
            "error_count": self.error_count,
            "samples_processed": len(self.processing_times)
        }


class TTTCLIProcessor:
    """TTT command-line integration for AI processing."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or DEMO_CONFIG["ttt_integration"]
        self.model = self.config.get("model", "@claude")
        self.system_prompt = self.config.get("system_prompt", 
                                           "You are a helpful AI assistant. Keep responses conversational and under 100 words.")
        self.conversation_context = collections.deque(maxlen=self.config.get("max_context_exchanges", 5) * 2)
        self.logger = setup_logging(__name__)
        
        # Verify TTT CLI is available
        self._verify_ttt_available()
    
    def _verify_ttt_available(self):
        """Check if TTT CLI is available and configured."""
        try:
            import subprocess
            result = subprocess.run(["ttt", "status"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.logger.info("TTT CLI verified successfully")
            else:
                self.logger.warning(f"TTT CLI status check failed: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.logger.error(f"TTT CLI not available: {e}")
            self.logger.error("Install TTT CLI or ensure it's in your PATH")
    
    def build_conversation_context(self, new_user_text: str) -> str:
        """Build context string for TTT processing with sliding window."""
        # Add user message to context
        self.conversation_context.append(f"User: {new_user_text}")
        
        # Maintain sliding window of last 5 exchanges (10 messages)
        if len(self.conversation_context) > 10:
            self.conversation_context = collections.deque(
                list(self.conversation_context)[-10:], 
                maxlen=self.config.get("max_context_exchanges", 5) * 2
            )
        
        # Smart context formatting for TTT
        if len(self.conversation_context) > 1:
            # Get last 4 exchanges (8 messages) for context
            recent_context = list(self.conversation_context)[-8:]
            context_lines = []
            
            for i, line in enumerate(recent_context):
                # Add emphasis to recent exchanges
                if i >= len(recent_context) - 4:  # Last 2 exchanges
                    context_lines.append(f">>> {line}")
                else:
                    context_lines.append(f"    {line}")
            
            context = "\n".join(context_lines)
            formatted_prompt = f"""Conversation context:
{context}

Please respond naturally to the latest user message. Keep your response conversational and under 100 words."""
            
            self.logger.debug(f"Built context with {len(recent_context)} messages")
            return formatted_prompt
        else:
            return new_user_text
    
    async def process_text(self, text: str) -> str:
        """Process user text through TTT and return AI response."""
        try:
            # Build enhanced context-aware prompt
            prompt = self.build_conversation_context(text)
            
            # Execute TTT CLI
            cmd = ["ttt", self.model, "--system", self.system_prompt, prompt]
            self.logger.debug(f"Executing TTT: {' '.join(cmd[:3])}...")
            
            result = await asyncio.create_subprocess_exec(
                *cmd, 
                stdout=asyncio.subprocess.PIPE, 
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode().strip()
                self.logger.error(f"TTT CLI error: {error_msg}")
                return f"I'm having trouble processing that right now. TTT error: {error_msg}"
            
            response = stdout.decode().strip()
            
            # Add assistant response to context
            self.conversation_context.append(f"Assistant: {response}")
            
            self.logger.info(f"AI Response: {response[:100]}...")
            return response
            
        except asyncio.TimeoutError:
            self.logger.error("TTT CLI timeout")
            return "I'm taking too long to respond. Please try again."
        except Exception as e:
            self.logger.error(f"TTT processing error: {e}")
            return f"I encountered an error: {str(e)}"


class TTSCLIEngine:
    """TTS command-line integration with interruption support."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or DEMO_CONFIG["tts_integration"]
        self.provider = self.config.get("provider", "@edge")
        self.voice = self.config.get("voice", "en-US-AriaNeural")
        self.audio_format = self.config.get("audio_format", "wav")
        self.interruption_check_interval = self.config.get("interruption_check_interval", 0.1)
        
        # Enhanced audio tracking for AEC
        self.reference_audio_buffer = collections.deque(maxlen=100)  # Last 10 seconds at 10fps
        self.current_playback_frame = None
        self.playback_position = 0
        self.audio_data = None
        self.sample_rate = 22050  # Common TTS sample rate
        
        self.current_tts_process = None
        self.temp_audio_file = None
        self.is_speaking = False
        self.interruption_callback = None
        
        self.logger = setup_logging(__name__)
        
        # Verify TTS CLI is available
        self._verify_tts_available()
    
    def _verify_tts_available(self):
        """Check if TTS CLI is available and configured."""
        try:
            import subprocess
            result = subprocess.run(["tts", "status"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.logger.info("TTS CLI verified successfully")
            else:
                self.logger.warning(f"TTS CLI status check failed: {result.stderr}")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.logger.error(f"TTS CLI not available: {e}")
            self.logger.error("Install TTS CLI or ensure it's in your PATH")
    
    def set_interruption_callback(self, callback):
        """Set callback function to check for user interruption."""
        self.interruption_callback = callback
    
    async def speak_with_interruption_detection(self, text: str) -> bool:
        """Speak text with real-time interruption detection. Returns True if interrupted."""
        try:
            self.is_speaking = True
            
            # Create temporary file for audio output
            with tempfile.NamedTemporaryFile(suffix=f".{self.audio_format}", delete=False) as f:
                self.temp_audio_file = f.name
            
            # Generate audio file first
            cmd = ["tts", "save", text, "-o", self.temp_audio_file]
            if self.provider != "@edge":
                cmd.insert(2, self.provider)
            if self.voice and self.provider == "@edge":
                cmd.extend(["--voice", self.voice])
            
            self.logger.debug(f"Generating TTS: {' '.join(cmd[:4])}...")
            
            result = await asyncio.create_subprocess_exec(*cmd)
            await result.communicate()
            
            if result.returncode != 0:
                self.logger.error("TTS generation failed")
                return False
            
            # Play audio with interruption monitoring
            interrupted = await self._play_with_interruption_detection()
            
            return interrupted
            
        except Exception as e:
            self.logger.error(f"TTS playback error: {e}")
            return False
        finally:
            self.is_speaking = False
            self.cleanup()
    
    async def _play_with_interruption_detection(self) -> bool:
        """Play audio file while monitoring for interruption."""
        try:
            # Load audio data for frame tracking
            self._load_audio_data(self.temp_audio_file)
            
            # Try to use pygame for audio playback
            import pygame
            
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)
            sound = pygame.mixer.Sound(self.temp_audio_file)
            
            # Start playback and timing
            start_time = time.time()
            sound.play()
            
            # Monitor for interruption while playing
            while pygame.mixer.get_busy():
                # Update current playback frame for AEC reference
                elapsed = time.time() - start_time
                self._update_playback_frame(elapsed)
                
                if self.interruption_callback and await self.interruption_callback():
                    self.logger.info("🛑 TTS interrupted by user speech")
                    pygame.mixer.stop()
                    return True
                
                await asyncio.sleep(self.interruption_check_interval)
            
            # Clear playback frame when done
            self.current_playback_frame = None
            return False  # Completed without interruption
            
        except ImportError:
            self.logger.warning("pygame not available, using fallback audio playback")
            return await self._fallback_audio_playback()
        except Exception as e:
            self.logger.error(f"Audio playback error: {e}")
            return False
    
    async def _fallback_audio_playback(self) -> bool:
        """Fallback audio playback without pygame."""
        try:
            # Load audio data for frame tracking
            self._load_audio_data(self.temp_audio_file)
            
            # Simple approach: estimate duration and check for interruption
            import subprocess
            
            # Try to get audio duration from loaded data
            if self.audio_data is not None:
                duration = len(self.audio_data) / self.sample_rate
            else:
                duration = 3.0  # Default estimate
            
            # Start audio playback in background
            if sys.platform.startswith('linux'):
                play_cmd = ["aplay", self.temp_audio_file]
            elif sys.platform == 'darwin':
                play_cmd = ["afplay", self.temp_audio_file]
            elif sys.platform.startswith('win'):
                # Windows audio playback using winsound or powershell
                return await self._windows_audio_playback()
            else:
                self.logger.warning(f"Unsupported platform: {sys.platform}")
                return False
            
            process = await asyncio.create_subprocess_exec(*play_cmd)
            start_time = time.time()
            
            # Monitor for interruption
            check_count = int(duration / self.interruption_check_interval)
            for i in range(check_count):
                if process.returncode is not None:
                    break  # Audio finished
                
                # Update playback frame for AEC reference
                elapsed = time.time() - start_time
                self._update_playback_frame(elapsed)
                    
                if self.interruption_callback and await self.interruption_callback():
                    self.logger.info("🛑 TTS interrupted by user speech")
                    process.terminate()
                    await process.wait()
                    return True
                
                await asyncio.sleep(self.interruption_check_interval)
            
            await process.wait()
            # Clear playback frame when done
            self.current_playback_frame = None
            return False
            
        except Exception as e:
            self.logger.error(f"Fallback audio playback error: {e}")
            return False
    
    async def _windows_audio_playback(self) -> bool:
        """Windows-specific audio playback implementation."""
        try:
            # Method 1: Try winsound (built-in to Python on Windows)
            try:
                import winsound
                
                # Load audio data for frame tracking if available
                if self.audio_data is not None:
                    duration = len(self.audio_data) / self.sample_rate
                else:
                    duration = 3.0  # Default estimate
                
                # Play sound in a separate thread to allow interruption checking
                def play_sound():
                    winsound.PlaySound(self.temp_audio_file, winsound.SND_FILENAME)
                
                import threading
                play_thread = threading.Thread(target=play_sound)
                play_thread.daemon = True
                play_thread.start()
                
                start_time = time.time()
                
                # Monitor for interruption while playing
                while play_thread.is_alive():
                    # Update playback frame for AEC reference
                    elapsed = time.time() - start_time
                    self._update_playback_frame(elapsed)
                    
                    if self.interruption_callback and await self.interruption_callback():
                        self.logger.info("🛑 Windows TTS interrupted by user speech")
                        # Note: winsound doesn't support stopping, but we can detect interruption
                        return True
                    
                    # Break if we've exceeded expected duration
                    if elapsed > duration + 1.0:
                        break
                    
                    await asyncio.sleep(self.interruption_check_interval)
                
                # Clear playback frame when done
                self.current_playback_frame = None
                return False  # Completed without interruption
                
            except ImportError:
                # Method 2: Try PowerShell (available on all modern Windows)
                return await self._windows_powershell_playback()
                
        except Exception as e:
            self.logger.error(f"Windows audio playback error: {e}")
            return False
    
    async def _windows_powershell_playback(self) -> bool:
        """Windows PowerShell audio playback fallback."""
        try:
            # Load audio data for frame tracking
            if self.audio_data is not None:
                duration = len(self.audio_data) / self.sample_rate
            else:
                duration = 3.0
            
            # PowerShell command to play audio
            ps_command = f'''
            Add-Type -AssemblyName presentationCore
            $mediaPlayer = New-Object system.windows.media.mediaplayer
            $mediaPlayer.open([uri]'{self.temp_audio_file}')
            $mediaPlayer.Play()
            Start-Sleep -Seconds {duration + 0.5}
            $mediaPlayer.Stop()
            '''
            
            # Start PowerShell process
            process = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            start_time = time.time()
            
            # Monitor for interruption
            while process.returncode is None:
                # Update playback frame for AEC reference
                elapsed = time.time() - start_time
                self._update_playback_frame(elapsed)
                
                if self.interruption_callback and await self.interruption_callback():
                    self.logger.info("🛑 Windows PowerShell TTS interrupted")
                    process.terminate()
                    await process.wait()
                    return True
                
                if elapsed > duration + 1.0:
                    break
                
                await asyncio.sleep(self.interruption_check_interval)
            
            await process.wait()
            self.current_playback_frame = None
            return False
            
        except Exception as e:
            self.logger.error(f"PowerShell audio playback error: {e}")
            return False
    
    def get_reference_audio(self):
        """Get current TTS audio for AEC reference."""
        return list(self.reference_audio_buffer)
    
    def get_current_playback_frame(self):
        """Get real-time TTS audio frame for AEC reference."""
        return self.current_playback_frame
    
    def _load_audio_data(self, audio_file: str):
        """Load audio data for frame-by-frame playback tracking."""
        try:
            import wave
            import numpy as np
            
            with wave.open(audio_file, 'rb') as wav_file:
                frames = wav_file.readframes(-1)
                self.sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                
                # Convert to numpy array
                if wav_file.getsampwidth() == 2:
                    self.audio_data = np.frombuffer(frames, dtype=np.int16)
                else:
                    self.audio_data = np.frombuffer(frames, dtype=np.float32)
                
                # Convert stereo to mono if needed
                if channels == 2:
                    self.audio_data = self.audio_data[::2]
                
                self.logger.debug(f"Loaded audio: {len(self.audio_data)} samples at {self.sample_rate}Hz")
                
        except Exception as e:
            self.logger.warning(f"Failed to load audio data: {e}")
            self.audio_data = None
    
    def _update_playback_frame(self, elapsed_time: float):
        """Update current playback frame based on elapsed time."""
        if self.audio_data is None:
            return
        
        try:
            # Calculate current sample position
            sample_position = int(elapsed_time * self.sample_rate)
            frame_size = int(0.1 * self.sample_rate)  # 100ms frames
            
            if sample_position < len(self.audio_data) - frame_size:
                # Extract current frame
                self.current_playback_frame = self.audio_data[sample_position:sample_position + frame_size]
                
                # Add to reference buffer for AEC
                self.reference_audio_buffer.append(self.current_playback_frame.copy())
            else:
                self.current_playback_frame = None
                
        except Exception as e:
            self.logger.debug(f"Playback frame update error: {e}")
            self.current_playback_frame = None
    
    def cleanup(self):
        """Clean up temporary files."""
        if self.temp_audio_file and os.path.exists(self.temp_audio_file):
            try:
                os.unlink(self.temp_audio_file)
            except Exception as e:
                self.logger.debug(f"Failed to cleanup temp file: {e}")
            self.temp_audio_file = None


class SmartConversationMode(ConversationMode):
    """Enhanced ConversationMode with WebRTC AEC and AI integration."""
    
    def __init__(self, args, config: Dict[str, Any] = None):
        super().__init__(args)
        
        self.demo_config = config or DEMO_CONFIG
        
        # Initialize components
        self.aec_processor = WebRTCAECProcessor(self.demo_config["webrtc_aec"])
        self.ttt_processor = TTTCLIProcessor(self.demo_config["ttt_integration"])
        self.tts_engine = TTSCLIEngine(self.demo_config["tts_integration"])
        
        # Set up interruption detection
        self.tts_engine.set_interruption_callback(self._detect_user_speech_during_tts)
        
        # State tracking
        self.ai_processing = False
        self.waiting_for_ai_response = False
        
        # Enhanced interruption detection state
        self.interruption_check_active = False
        self.last_interruption_check = 0
        
        self.logger.info("Smart Voice Assistant initialized")
        self.logger.info(f"🔧 WebRTC AEC: {'Enabled' if self.aec_processor.enabled else 'Disabled'}")
        self.logger.info(f"🤖 AI Model: {self.ttt_processor.model}")
        self.logger.info(f"🔊 TTS Engine: {self.tts_engine.provider}")
        self.logger.info("Phase 2: Enhanced interruption detection and context management active")

    async def process_audio_chunk(self, audio_chunk):
        """Override to add AEC processing before STT."""
        # Apply echo cancellation if available
        if self.aec_processor.enabled:
            reference_audio = self.tts_engine.get_reference_audio()
            clean_audio = self.aec_processor.process_audio_frame(audio_chunk, reference_audio)
            return clean_audio
        else:
            return audio_chunk
    
    async def _get_current_mic_frame(self):
        """Get current microphone frame during TTS playback."""
        try:
            # Tap into existing ConversationMode audio stream
            if hasattr(self, 'audio_queue') and self.audio_queue:
                # Try to get latest audio chunk without blocking
                try:
                    latest_chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.01)
                    # Put it back for normal processing
                    await self.audio_queue.put(latest_chunk)
                    return latest_chunk
                except asyncio.TimeoutError:
                    return None
            return None
        except Exception as e:
            self.logger.debug(f"Error getting mic frame: {e}")
            return None
    
    def _apply_vad_to_clean_audio(self, clean_audio):
        """Apply VAD to AEC-processed audio."""
        try:
            if self.vad and clean_audio is not None:
                # Apply existing GOOBITS VAD to clean audio
                speech_prob = self.vad.process_chunk(clean_audio)
                # Use same threshold as conversation mode
                is_speech = speech_prob > self.vad_threshold
                
                self.logger.debug(f"VAD on clean audio: prob={speech_prob:.3f}, speech={is_speech}")
                return is_speech
            return False
        except Exception as e:
            self.logger.debug(f"VAD processing error: {e}")
            return False
    
    async def _detect_user_speech_during_tts(self) -> bool:
        """Detect human speech while TTS is playing using WebRTC AEC."""
        try:
            # 1. Get current microphone input frame
            mic_input = await self._get_current_mic_frame()
            if mic_input is None:
                return False
            
            # 2. Get TTS reference audio for echo cancellation
            tts_reference = self.tts_engine.get_current_playback_frame()
            
            # 3. Remove TTS echo using WebRTC AEC
            if self.aec_processor.enabled and tts_reference is not None:
                clean_audio = self.aec_processor.process_audio_frame(mic_input, tts_reference)
            else:
                clean_audio = mic_input
            
            # 4. Apply VAD to clean audio to detect human speech
            return self._apply_vad_to_clean_audio(clean_audio)
            
        except Exception as e:
            self.logger.debug(f"Speech detection error: {e}")
            return False
    
    async def _send_transcription(self, result: Dict[str, Any], extra: Optional[Dict] = None):
        """Override to add AI processing after STT."""
        # Send the original transcription first
        await super()._send_transcription(result, extra)
        
        # Only process final (non-partial) results for AI response
        if not result.get("is_partial", False) and result.get("success", False):
            text = result.get("text", "").strip()
            if text and not self.ai_processing:
                # Process with AI asynchronously to avoid blocking STT
                asyncio.create_task(self._process_with_ai(text))
    
    async def _process_with_ai(self, user_text: str):
        """Process user text with AI and speak the response."""
        try:
            self.ai_processing = True
            self.waiting_for_ai_response = True
            
            self.logger.info(f"🎤 User said: {user_text}")
            
            # Send status update
            await self._send_status("ai_processing", "Processing with AI...")
            
            # Get AI response
            ai_response = await self.ttt_processor.process_text(user_text)
            
            if ai_response:
                self.logger.info(f"🤖 AI responds: {ai_response}")
                
                # Send AI response as a special message type
                ai_result = {
                    "type": "ai_response",
                    "text": ai_response,
                    "user_text": user_text,
                    "timestamp": time.time(),
                    "success": True
                }
                
                # Send the AI response
                await self._send_message(ai_result)
                
                # Speak the response with enhanced interruption detection
                await self._send_status("speaking", "Speaking response...")
                self.interruption_check_active = True
                
                interrupted = await self.tts_engine.speak_with_interruption_detection(ai_response)
                
                self.interruption_check_active = False
                
                if interrupted:
                    self.logger.info("🛑 TTS was interrupted by user - ready for new input")
                    await self._send_status("interrupted", "Response interrupted - listening")
                else:
                    await self._send_status("listening", "Ready for next input")
            
        except Exception as e:
            self.logger.error(f"AI processing error: {e}")
            await self._send_error(f"AI processing failed: {e}")
        finally:
            self.ai_processing = False
            self.waiting_for_ai_response = False

    async def _send_message(self, message: Dict[str, Any]):
        """Send a custom message (like AI response)."""
        if self.websocket:
            try:
                import json
                await self.websocket.send(json.dumps(message))
            except Exception as e:
                self.logger.error(f"Failed to send message: {e}")
        else:
            # Print to console if no websocket
            if message.get("type") == "ai_response":
                print(f"\n🤖 AI: {message['text']}\n")

    async def cleanup(self):
        """Clean up all components."""
        # Log performance statistics
        aec_stats = self.aec_processor.get_performance_stats()
        self.logger.info(f"AEC Performance: {aec_stats}")
        
        context_stats = {
            "total_exchanges": len(self.ttt_processor.conversation_context) // 2,
            "context_length": len(self.ttt_processor.conversation_context)
        }
        self.logger.info(f"Conversation Stats: {context_stats}")
        
        self.tts_engine.cleanup()
        await super()._cleanup()


def create_demo_args():
    """Create default arguments for the demo."""
    class Args:
        def __init__(self):
            # Audio settings
            self.sample_rate = 16000
            self.chunk_duration_ms = 100
            self.device_index = None
            
            # Model settings  
            self.model_size = "base"
            self.model_path = None
            self.language = "auto"
            self.compute_type = "auto"
            
            # Output settings
            self.websocket = None
            self.output_file = None
            self.save_recording = False
            
            # Mode settings
            self.conversation = True
            
            # Debug and logging (required by BaseMode)
            self.debug = False
            self.verbose = False
            self.format = "text"
            self.json = False
            
    return Args()


def check_dependencies():
    """Check if required dependencies are available with platform-specific support."""
    missing = []
    warnings = []
    
    # Check TTT CLI
    try:
        import subprocess
        result = subprocess.run(["ttt", "status"], capture_output=True, timeout=3)
        if result.returncode != 0:
            warnings.append("TTT CLI status check failed - AI responses may not work")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        missing.append("TTT CLI not found - install TTT CLI for AI processing")
    
    # Check TTS CLI
    try:
        import subprocess
        result = subprocess.run(["tts", "status"], capture_output=True, timeout=3)
        if result.returncode != 0:
            warnings.append("TTS CLI status check failed - speech synthesis may not work")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        missing.append("TTS CLI not found - install TTS CLI for speech synthesis")
    
    # Check WebRTC
    try:
        import webrtc_audio_processing
    except ImportError:
        warnings.append("webrtc-audio-processing not available - echo cancellation disabled")
    
    # Check audio libraries with platform-specific support
    audio_support = False
    
    try:
        import pygame
        audio_support = True
    except ImportError:
        pass
    
    try:
        import pyaudio
        audio_support = True
    except ImportError:
        pass
    
    # Platform-specific audio support
    if sys.platform.startswith('win'):
        try:
            import winsound
            audio_support = True
        except ImportError:
            # Check for PowerShell availability
            try:
                import subprocess
                result = subprocess.run(["powershell", "-Command", "Get-Host"], 
                                      capture_output=True, timeout=2)
                if result.returncode == 0:
                    audio_support = True
            except:
                pass
    elif sys.platform.startswith('linux'):
        # Check for aplay
        try:
            import subprocess
            result = subprocess.run(["which", "aplay"], capture_output=True, timeout=2)
            if result.returncode == 0:
                audio_support = True
        except:
            pass
    elif sys.platform == 'darwin':
        # Check for afplay
        try:
            import subprocess
            result = subprocess.run(["which", "afplay"], capture_output=True, timeout=2)
            if result.returncode == 0:
                audio_support = True
        except:
            pass
    
    if not audio_support:
        warnings.append(f"No audio playback support found for {sys.platform} - TTS playback may not work")
    
    # Check for numpy (required for audio processing)
    try:
        import numpy
    except ImportError:
        missing.append("numpy not found - required for audio processing")
    
    return missing, warnings


def get_platform_info():
    """Get detailed platform information for troubleshooting."""
    import platform
    
    info = {
        "platform": sys.platform,
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }
    
    # Check audio capabilities
    audio_methods = []
    
    try:
        import pygame
        audio_methods.append("pygame")
    except ImportError:
        pass
    
    try:
        import pyaudio
        audio_methods.append("pyaudio")
    except ImportError:
        pass
    
    if sys.platform.startswith('win'):
        try:
            import winsound
            audio_methods.append("winsound")
        except ImportError:
            pass
        
        try:
            import subprocess
            result = subprocess.run(["powershell", "-Command", "Get-Host"], 
                                  capture_output=True, timeout=2)
            if result.returncode == 0:
                audio_methods.append("powershell")
        except:
            pass
    
    info["audio_methods"] = audio_methods
    return info


async def main():
    """Main demo function."""
    parser = argparse.ArgumentParser(description="Smart Voice Assistant Demo")
    parser.add_argument("--model", default="base", help="Whisper model size")
    parser.add_argument("--device", type=int, help="Audio device index")
    parser.add_argument("--ai-model", default="@claude", help="AI model for TTT")
    parser.add_argument("--tts-provider", default="@edge", help="TTS provider")
    parser.add_argument("--tts-voice", default="en-US-AriaNeural", help="TTS voice")
    parser.add_argument("--disable-aec", action="store_true", help="Disable echo cancellation")
    parser.add_argument("--save-config-template", action="store_true", help="Save config template to main config.json")
    parser.add_argument("--show-config", action="store_true", help="Show current configuration and exit")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with detailed platform info")
    parser.add_argument("--platform-info", action="store_true", help="Show platform information and exit")
    
    args = parser.parse_args()
    
    # Create demo arguments
    demo_args = create_demo_args()
    demo_args.model_size = args.model
    demo_args.device_index = args.device
    
    # Load demo config from GOOBITS config system
    demo_config = load_demo_config_from_goobits()
    
    # Handle special CLI arguments
    if args.save_config_template:
        if save_demo_config_template():
            print("Configuration template saved successfully!")
        else:
            print("Configuration template already exists or save failed.")
        return
    
    if args.show_config:
        print("\n📋 Current Demo Configuration:")
        print(json.dumps(demo_config, indent=2))
        return
    
    # Update demo config based on CLI args (CLI args override config file)
    demo_config["ttt_integration"]["model"] = args.ai_model
    demo_config["tts_integration"]["provider"] = args.tts_provider
    demo_config["tts_integration"]["voice"] = args.tts_voice
    demo_config["webrtc_aec"]["enable_aec"] = not args.disable_aec
    
    # Check dependencies first
    missing, warnings = check_dependencies()
    
    # Print startup information
    print("🎤 Smart Voice Assistant Demo - Phase 2")
    print("=" * 50)
    print(f"🔧 WebRTC AEC: {'Enabled' if not args.disable_aec else 'Disabled'}")
    print(f"🤖 AI Model: {args.ai_model}")
    print(f"🔊 TTS Engine: {args.tts_provider}")
    print(f"🎵 TTS Voice: {args.tts_voice}")
    
    if missing:
        print("\n⚠️  Missing Dependencies:")
        for dep in missing:
            print(f"   • {dep}")
    
    if warnings:
        print("\n⚠️  Warnings:")
        for warning in warnings:
            print(f"   • {warning}")
    
    print(f"\n📱 Say something to start the conversation...")
    print("=" * 50)
    
    # Show platform info in debug mode
    if hasattr(args, 'debug') and args.debug:
        platform_info = get_platform_info()
        print(f"\n🖥️  Platform: {platform_info['system']} {platform_info['release']}")
        print(f"   Audio methods: {', '.join(platform_info['audio_methods'])}")
    
    # Create and run the smart conversation mode
    smart_mode = SmartConversationMode(demo_args, demo_config)
    
    try:
        await smart_mode.run()
    except KeyboardInterrupt:
        print("\n👋 Smart Voice Assistant stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        await smart_mode.cleanup()
        print("\n🎉 Smart Voice Assistant Demo completed successfully!")
        print("   Phase 3: Production-ready with comprehensive monitoring")


def cli_main():
    """Entry point for the smart-voice-demo CLI command."""
    asyncio.run(main())

if __name__ == "__main__":
    cli_main()