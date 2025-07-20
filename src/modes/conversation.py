#!/usr/bin/env python3
"""
Conversation Mode - Continuous VAD-based listening for hands-free operation

This mode enables continuous, hands-free listening with:
- Voice Activity Detection (VAD) to detect speech
- Automatic transcription of each utterance
- Immediate return to listening state after transcription
- Interruption support for new speech while processing
"""

import asyncio
import collections
import difflib
import threading
import time
from typing import Dict, Any, Optional
from pathlib import Path
import sys

# Add project root to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.absolute()))

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

# Text formatting for streaming results
try:
    from src.text_formatting import TextFormatter
    TEXT_FORMATTING_AVAILABLE = True
except ImportError:
    TEXT_FORMATTING_AVAILABLE = False
    TextFormatter = None


class ConversationMode(BaseMode):
    """Continuous conversation mode with VAD-based utterance detection."""

    def __init__(self, args, wake_word_callback=None):
        super().__init__(args)
        
        # Wake word integration
        self.wake_word_callback = wake_word_callback
        # Load exit phrases from wake_word config if available, otherwise use defaults
        wake_word_config = self.config.get("wake_word", {})
        self.exit_phrases = wake_word_config.get("exit_phrases", [
            "goodbye jarvis", 
            "stop listening", 
            "sleep jarvis"
        ])
        
        # Load VAD parameters from config
        mode_config = self._get_mode_config()
        
        # Load streaming configuration (Phase 4)
        streaming_config = self.config.get("streaming", {})
        self.enable_partial_results = streaming_config.get("enable_partial_results", True)
        self.chunk_processing_interval_ms = streaming_config.get("chunk_processing_interval_ms", 500)
        self.agreement_threshold = streaming_config.get("agreement_threshold", 2)
        self.context_window_s = streaming_config.get("context_window_s", 3)
        self.max_buffer_duration_s = streaming_config.get("max_buffer_duration_s", 30)
        self.confidence_levels = streaming_config.get("confidence_levels", ["confirmed", "provisional", "pending"])
        
        # VAD and transcription
        self.is_listening = False
        self.is_processing = False
        self.chunks_per_second = 10  # 100ms chunks
        # Dual-buffer architecture for enhanced VAD handling
        self.pre_buffer_duration_s = mode_config.get("pre_buffer_duration_s", 5.0)  # 5 seconds continuous rolling
        self.segment_max_duration_s = mode_config.get("segment_max_duration_s", 25.0)  # Process in 25s segments  
        self.segment_overlap_duration_s = mode_config.get("segment_overlap_duration_s", 5.0)  # Overlap for context

        # Pre-buffer: always-on circular buffer for speech onset capture
        pre_buffer_chunks = int(self.pre_buffer_duration_s * self.chunks_per_second)
        self.pre_buffer = collections.deque(maxlen=pre_buffer_chunks)

        # Main buffer: dynamic list for utterance processing (no hard limit)
        self.main_buffer = []
        self.segment_max_chunks = int(self.segment_max_duration_s * self.chunks_per_second)
        self.overlap_chunks = int(self.segment_overlap_duration_s * self.chunks_per_second)

        # Deduplication tracking
        self.last_buffer_hash = None
        self.processing_count = 0
        self.max_processing_count = 3
        
        # Long utterance accumulation tracking
        self.accumulated_segments = []  # Store transcribed segments from long utterances
        self.current_utterance_start_time = None
        self.segment_count = 0
        
        # VAD-based speech timing
        self.speech_start_chunk_idx = None  # Index in main_buffer where speech actually started
        self.speech_end_chunk_idx = None    # Index where speech ended
        self.total_chunks_processed = 0     # Total chunks seen since utterance start
        self.vad = None  # Silero VAD instance
        self.vad_threshold = mode_config.get("vad_threshold", 0.5)
        self.min_speech_duration = mode_config.get("min_speech_duration_s", 0.5)
        self.max_silence_duration = mode_config.get("max_silence_duration_s", 1.0)
        self.speech_pad_duration = mode_config.get("speech_pad_duration_s", 0.3)

        # VAD state machine
        self.vad_state = "silence"  # silence, speech, trailing
        self.consecutive_speech = 0
        self.consecutive_silence = 0

        # Threading
        self.processing_thread = None
        self.stop_event = threading.Event()
        
        # Streaming transcription (Phase 0 & 1)
        self.last_transcription = ""
        self.last_partial_time = 0
        self.partial_processing_interval = self.chunk_processing_interval_ms / 1000.0  # Convert ms to seconds
        
        # LocalAgreement-2 state (Phase 1)
        self.previous_partial_result = ""
        self.confirmed_text = ""
        
        # Context preservation (Phase 2)
        self.conversation_context = ""  # Running context for Whisper prompts
        
        # Interruption handling (Phase 3)
        self.final_processing_task = None  # Track finalization task for cancellation
        self.partial_processing_task = None  # Track partial processing task for cancellation
        self.last_utterance_hash = None  # Track utterance changes
        self.processing_count = 0  # Rate limiting counter
        
        # Text formatting (Phase 4)
        self.text_formatter = None
        if TEXT_FORMATTING_AVAILABLE:
            try:
                self.text_formatter = TextFormatter(language='en')  # TODO: get from config
                self.logger.info("Text formatting enabled for streaming results")
            except Exception as e:
                self.logger.warning(f"Text formatting initialization failed: {e}")
                self.text_formatter = None
        
        self.logger.info(f"VAD config: threshold={self.vad_threshold}, "
                        f"min_speech={self.min_speech_duration}s, "
                        f"max_silence={self.max_silence_duration}s")
        self.logger.info(f"Streaming config: interval={self.chunk_processing_interval_ms}ms, "
                        f"buffer={self.max_buffer_duration_s}s, "
                        f"partial_enabled={self.enable_partial_results}")

    async def run(self):
        """Main conversation mode loop."""
        try:
            # Initialize Whisper model
            await self._load_model()

            # Initialize VAD
            await self._initialize_vad()

            # Start audio streaming
            await self._start_audio_streaming()

            # Send initial status
            await self._send_status("listening", "Conversation mode active - speak naturally")

            # Main processing loop
            await self._conversation_loop()

        except KeyboardInterrupt:
            await self._send_status("interrupted", "Conversation mode stopped by user")
        except Exception as e:
            self.logger.exception(f"Conversation mode error: {e}")
            await self._send_error(f"Conversation mode failed: {e}")
        finally:
            await self._cleanup()


    async def _initialize_vad(self):
        """Initialize Silero VAD in executor to avoid blocking."""
        try:
            from src.audio.vad import SileroVAD
            self.logger.info("Initializing Silero VAD...")

            loop = asyncio.get_event_loop()
            self.vad = await loop.run_in_executor(
                None,
                lambda: SileroVAD(
                    sample_rate=self.args.sample_rate,
                    threshold=self.vad_threshold,
                    min_speech_duration=self.min_speech_duration,
                    min_silence_duration=self.max_silence_duration,
                    use_onnx=True  # Faster inference
                )
            )

            self.logger.info("Silero VAD initialized successfully")
        except ImportError as e:
            self.logger.error(f"VAD dependencies not available: {e}")
            self.logger.error("Install dependencies with: pip install torch torchaudio silero-vad")
            raise RuntimeError(f"VAD initialization failed: {e}")
        except Exception as e:
            self.logger.error(f"Failed to initialize VAD: {e}")
            raise

    async def _start_audio_streaming(self):
        """Initialize audio streaming."""
        try:
            await self._setup_audio_streamer(maxsize=300)  # Larger buffer for streaming processing

            # Start recording
            if not self.audio_streamer.start_recording():
                raise RuntimeError("Failed to start audio recording")

            self.logger.info("Audio streaming started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start audio streaming: {e}")
            raise

    async def _conversation_loop(self):
        """Main conversation processing loop."""
        self.is_listening = True
        speech_start = None

        while not self.stop_event.is_set():
            try:
                # Get audio chunk with timeout
                if self.audio_queue is None:
                    break
                audio_chunk = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)

                # Get speech probability from Silero VAD
                if self.vad is None:
                    break
                speech_prob = self.vad.process_chunk(audio_chunk)

                # Advanced VAD with hysteresis and state machine
                if speech_prob > self.vad_threshold:
                    self.consecutive_speech += 1
                    self.consecutive_silence = 0

                    if self.vad_state == "silence" and self.consecutive_speech >= 2:
                        # Require 2 consecutive speech chunks to start
                        self.vad_state = "speech"
                        if speech_start is None:
                            speech_start = time.time() - (0.1 * self.consecutive_speech)  # Backdate start
                            
                            # Phase 3: Cancel any ongoing final processing for interruption handling
                            if self.final_processing_task and not self.final_processing_task.done():
                                self.logger.debug("Cancelling previous final processing due to new speech")
                                self.final_processing_task.cancel()
                                self.final_processing_task = None
                                self.is_processing = False
                            
                            # Merge pre-buffer into main buffer with padding
                            padding_chunks = int(0.5 * self.chunks_per_second)  # 500ms padding
                            pre_buffer_list = list(self.pre_buffer)
                            self.main_buffer = pre_buffer_list[-padding_chunks:] + self.main_buffer
                            
                            # Initialize long utterance tracking
                            self.accumulated_segments = []
                            self.current_utterance_start_time = time.time()
                            self.segment_count = 0
                            
                            self.last_transcription = ""  # Reset for new utterance
                            self.previous_partial_result = ""  # Reset LocalAgreement-2 state
                            self.confirmed_text = ""
                            self.last_partial_time = time.time()
                            
                            self.logger.info(f"🎤 NEW UTTERANCE STARTED (prob: {speech_prob:.3f})")
                            self.logger.info(f"   📊 Merged {len(pre_buffer_list[-padding_chunks:])} pre-buffer chunks")
                            self.logger.info(f"   🔧 Reset accumulated segments, starting fresh tracking")

                    # ALWAYS fill pre-buffer regardless of VAD state
                    self.pre_buffer.append(audio_chunk)

                    # Only add to main buffer during speech
                    if self.vad_state == "speech" and speech_start is not None:
                        self.main_buffer.append(audio_chunk)
                        self.total_chunks_processed += 1
                        
                        # Check if we need to segment long utterances
                        if len(self.main_buffer) % 50 == 0:  # Check every 50 chunks (5 seconds)
                            buffer_duration = len(self.main_buffer) / self.chunks_per_second
                            self.logger.debug(f"📊 Buffer check: {buffer_duration:.1f}s ({len(self.main_buffer)} chunks)")
                            asyncio.create_task(self._check_buffer_segmentation())
                        
                        # Phase 0: Process partial results during speech (if enabled)
                        if self.enable_partial_results and self.vad_state == "speech":
                            current_time = time.time()
                            if (current_time - self.last_partial_time >= self.partial_processing_interval and 
                                len(self.main_buffer) > 5):  # At least minimum audio chunks
                                await self._process_partial_utterance()
                                self.last_partial_time = current_time
                            
                elif speech_prob < (self.vad_threshold - 0.15):  # Hysteresis
                    self.consecutive_silence += 1
                    self.consecutive_speech = 0

                    # Continue pre-buffering during silence
                    self.pre_buffer.append(audio_chunk)
                    
                    if self.vad_state == "speech":
                        # We're in speech, add to main buffer even during brief silence
                        if speech_start is not None:
                            self.main_buffer.append(audio_chunk)
                        self.total_chunks_processed += 1

                        # Check if silence is long enough to end utterance
                        required_silence = int(self.max_silence_duration * self.chunks_per_second)
                        if self.consecutive_silence >= required_silence:
                            # Calculate speech duration
                            if speech_start is not None:
                                speech_duration = time.time() - speech_start

                                if speech_duration >= self.min_speech_duration:
                                    # Valid utterance, process it as a task for interruption handling
                                    # Mark end of speech for VAD-based trimming
                                    self.speech_end_chunk_idx = len(self.main_buffer)
                                    
                                    self.logger.warning(f"🛑 UTTERANCE COMPLETE ({speech_duration:.2f}s) - Processing final result...")
                                    self.logger.info(f"   📍 Speech ended at buffer index {self.speech_end_chunk_idx}")
                                    self.vad_state = "silence"
                                    
                                    # Cancel any ongoing partial processing when transitioning to silence
                                    await self._cancel_partial_processing()
                                    
                                    # Phase 3: Use task-based final processing for cancellation support
                                    self.final_processing_task = asyncio.create_task(
                                        self._process_final_utterance_with_interruption()
                                    )
                                    
                                    speech_start = None
                                    self.consecutive_speech = 0
                                    self.consecutive_silence = 0
                                else:
                                    # Too short, reset
                                    self.logger.debug(f"Speech too short ({speech_duration:.2f}s), ignoring")
                                    self.logger.info(f"❌ UTTERANCE TOO SHORT ({speech_duration:.2f}s < {self.min_speech_duration}s) - Discarding")
                                    self.vad_state = "silence"
                                    speech_start = None
                                    await self._cancel_partial_processing()
                                    self.main_buffer.clear()  # Clear main buffer
                                    # CLEAN SLATE: Clear all tracking for new utterance
                                    self.accumulated_segments.clear()
                                    self.speech_start_chunk_idx = None
                                    self.speech_end_chunk_idx = None
                                    self.total_chunks_processed = 0
                                    self.last_transcription = ""
                                    self.previous_partial_result = ""
                                    self.confirmed_text = ""
                                    self.last_utterance_hash = None
                else:
                    # In the hysteresis zone, maintain current state
                    # Continue pre-buffering in all states
                    self.pre_buffer.append(audio_chunk)
                    
                    if self.vad_state == "speech" and speech_start is not None:
                        self.main_buffer.append(audio_chunk)
                        self.total_chunks_processed += 1

            except asyncio.TimeoutError:
                # No audio data - continue loop
                # Optionally log queue size if it's getting full
                if hasattr(self, 'audio_queue') and self.audio_queue and self.audio_queue.qsize() > 250:
                    self.logger.debug(f"Audio queue getting full: {self.audio_queue.qsize()}/300")
                continue
            except Exception as e:
                self.logger.error(f"Error in conversation loop: {e}")
                break

    async def _cancel_partial_processing(self):
        """Cancel any ongoing partial processing task."""
        if self.partial_processing_task and not self.partial_processing_task.done():
            self.logger.debug("Cancelling previous partial processing task")
            self.partial_processing_task.cancel()
            try:
                await self.partial_processing_task
            except asyncio.CancelledError:
                pass
            self.partial_processing_task = None
            self.processing_count = 0

    async def _check_buffer_segmentation(self):
        """Check if main buffer needs segmentation for long utterances."""
        if len(self.main_buffer) > self.segment_max_chunks:
            duration_s = len(self.main_buffer) / self.chunks_per_second
            self.logger.warning(f"🚨 LONG UTTERANCE DETECTED: {duration_s:.1f}s ({len(self.main_buffer)} chunks > {self.segment_max_chunks})")
            self.logger.warning(f"   ✂️  Segmenting buffer to prevent overflow...")
            await self._process_buffer_segment()

    async def _process_buffer_segment(self):
        """Process a segment of the buffer and maintain overlap."""
        try:
            self.segment_count += 1
            
            # Extract segment for processing - ONLY speech portion if VAD timing available
            if self.speech_start_chunk_idx is not None:
                # Trim to speech portion with small cushion
                cushion_chunks = int(0.3 * self.chunks_per_second)  # 300ms cushion
                start_idx = max(0, self.speech_start_chunk_idx - cushion_chunks)
                segment_end = min(len(self.main_buffer), start_idx + self.segment_max_chunks)
                segment_chunks = self.main_buffer[start_idx:segment_end]
                
                self.logger.warning(f"   📝 VAD-TRIMMED SEGMENT #{self.segment_count} (buffer {start_idx}:{segment_end})")
            else:
                # Fallback: use regular segmentation
                segment_chunks = self.main_buffer[:self.segment_max_chunks]
                self.logger.warning(f"   📝 REGULAR SEGMENT #{self.segment_count} (no VAD timing)")
                
            segment_duration = len(segment_chunks) / self.chunks_per_second
            self.logger.warning(f"   📏 Segment size: {segment_duration:.1f}s, {len(segment_chunks)} chunks")

            # Convert to audio array for transcription
            if segment_chunks:
                segment_audio = np.concatenate(segment_chunks)

                # Transcribe segment with ONLY conversation context (NOT accumulated segments)
                loop = asyncio.get_event_loop()
                # CRITICAL FIX: Do not use accumulated segments as context - causes feedback loop!
                context_prompt = self.conversation_context.strip()
                
                self.logger.info(f"   🧠 Context for segment: '{context_prompt[:100]}...'") 
                
                result = await loop.run_in_executor(
                    None,
                    lambda: self._transcribe_audio_with_vad_stats(segment_audio, context_prompt.strip())
                )

                if result.get("success"):
                    segment_text = result["text"].strip()
                    
                    # Store segment for final accumulation
                    segment_info = {
                        "text": segment_text,
                        "segment_number": self.segment_count,
                        "duration": segment_duration,
                        "timestamp": time.time()
                    }
                    self.accumulated_segments.append(segment_info)
                    
                    self.logger.warning(f"   ✅ SEGMENT #{self.segment_count} TRANSCRIBED: '{segment_text[:60]}...'")
                    self.logger.info(f"   📊 Total accumulated segments: {len(self.accumulated_segments)}")
                    
                    # CRITICAL FIX: Do NOT send accumulated partial results - causes context contamination!
                    # Just log the segment, don't send to output until final assembly
                    self.logger.info(f"   💫 Segment stored for final assembly (not sent as partial)")

            # Keep overlap for context continuity  
            remaining_chunks = len(self.main_buffer) - (self.segment_max_chunks - self.overlap_chunks)
            self.main_buffer = self.main_buffer[self.segment_max_chunks - self.overlap_chunks:]
            
            self.logger.warning(f"   ♾️  Trimmed buffer: {remaining_chunks} chunks remaining ({remaining_chunks/self.chunks_per_second:.1f}s)")

        except Exception as e:
            self.logger.error(f"Error processing buffer segment: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    async def _process_partial_utterance(self) -> None:
        """Process partial utterance for streaming results with LocalAgreement-2."""
        # Guard: Only process during active speech
        if self.vad_state != "speech":
            self.logger.debug("Skipping partial processing - not in speech state")
            return
            
        if not self.main_buffer:
            return
        
        # Rate limiting: Prevent multiple simultaneous partial processing tasks
        if self.processing_count > 0:
            self.logger.debug("Skipping partial processing - another task in progress")
            return
        
        # Cancel previous partial processing task
        await self._cancel_partial_processing()
        
        # Check if utterance buffer has actually changed
        utterance_data = np.concatenate(self.main_buffer)
        utterance_hash = hash(bytes(utterance_data.astype(np.int16).tobytes()))
        if utterance_hash == self.last_utterance_hash:
            self.logger.debug("Skipping partial processing - utterance unchanged")
            return
        
        # Start new partial processing task
        self.partial_processing_task = asyncio.create_task(
            self._do_partial_processing(utterance_data, utterance_hash)
        )

    async def _do_partial_processing(self, utterance_data: np.ndarray, utterance_hash: int) -> None:
        """Actual partial processing implementation."""
        self.processing_count += 1
        self.last_utterance_hash = utterance_hash

        try:
            # Double-check we're still in speech state before processing
            if self.vad_state != "speech":
                self.logger.debug("Aborting partial processing - no longer in speech state")
                return
                
            # Process in executor to avoid blocking the listening loop
            # Use ONLY conversation context (NOT confirmed_text to prevent feedback)
            loop = asyncio.get_event_loop()
            context_prompt = self.conversation_context.strip()
            result = await loop.run_in_executor(None, lambda: self._transcribe_audio_with_vad_stats(utterance_data, context_prompt))

            # Check if task was cancelled during processing
            if asyncio.current_task().cancelled():
                self.logger.debug("Partial processing was cancelled")
                return

            if result["success"]:
                new_transcription = result["text"].strip()
                
                # LocalAgreement-2: Find stable prefix using advanced agreement scoring
                stable_prefix = self._calculate_stable_prefix(self.previous_partial_result, new_transcription)
                
                # Only emit if the confirmed text has grown
                if len(stable_prefix) > len(self.confirmed_text):
                    self.confirmed_text = stable_prefix
                    
                    if self.confirmed_text:  # Only send non-empty confirmed text
                        # Calculate provisional text (remainder of latest transcription)
                        provisional_text = new_transcription[len(stable_prefix):]
                        
                        # Apply streaming-aware text formatting
                        formatted_confirmed = self._format_text_for_streaming(self.confirmed_text, is_partial=True)
                        formatted_provisional = self._format_text_for_streaming(provisional_text, is_partial=True)
                        
                        # Send the confirmed + provisional partial result
                        partial_result = {
                            "text": formatted_confirmed + (" " + formatted_provisional if formatted_provisional else ""),
                            "confirmed_text": formatted_confirmed,
                            "provisional_text": formatted_provisional,
                            "is_partial": True,
                            "status": "partial",
                            "success": True,
                            "language": "auto",  # Add required field
                            "duration": 0.0,     # Add required field
                            "confidence": 0.7,   # Add required field for base method
                            "streaming_confidence": {
                                "confirmed": 0.9,   # High confidence for agreed-upon text
                                "provisional": 0.5  # Lower confidence for changing text
                            },
                            "timestamp": time.time()
                        }
                        await self._send_transcription(partial_result)
                        
                        self.logger.debug(f"Confirmed: '{self.confirmed_text}', Provisional: '{provisional_text}'")
                
                # Update state for next comparison
                self.previous_partial_result = new_transcription

        except asyncio.CancelledError:
            self.logger.debug("Partial processing cancelled gracefully")
            # Don't re-raise, just clean up gracefully
        except Exception as e:
            self.logger.debug(f"Error processing partial utterance: {e}")
            # Log more details for debugging
            self.logger.debug(f"Utterance chunks: {len(self.main_buffer)}, Context: '{self.conversation_context[:50]}...'")
            # Don't re-raise - partial results are optional
        finally:
            self.processing_count = max(0, self.processing_count - 1)
            self.partial_processing_task = None

    async def _process_final_utterance_with_interruption(self) -> None:
        """Process the final complete utterance with interruption support."""
        
        total_duration = time.time() - self.current_utterance_start_time if self.current_utterance_start_time else 0
        
        self.logger.warning(f"🏁 FINALIZING UTTERANCE (duration: {total_duration:.1f}s)")
        self.logger.warning(f"   📊 Accumulated segments: {len(self.accumulated_segments)}")
        self.logger.warning(f"   📊 Remaining buffer: {len(self.main_buffer)} chunks ({len(self.main_buffer)/self.chunks_per_second:.1f}s)")
        
        # Log accumulated segments for debugging
        for i, seg in enumerate(self.accumulated_segments):
            self.logger.info(f"   Segment {i+1}: '{seg['text'][:50]}...'")
        
        final_text_parts = []
        
        # Add all accumulated segments
        for segment in self.accumulated_segments:
            if segment["text"].strip():
                final_text_parts.append(segment["text"].strip())
                
        # Process remaining buffer if it has content - USE VAD-BASED TRIMMING
        if self.main_buffer:
            self.is_processing = True
            
            try:
                # CRITICAL FIX: Only process speech portion with small cushion
                if self.speech_start_chunk_idx is not None and self.speech_end_chunk_idx is not None:
                    # Add small cushion (0.5s = 5 chunks on each side)
                    cushion_chunks = int(0.5 * self.chunks_per_second)
                    start_idx = max(0, self.speech_start_chunk_idx - cushion_chunks)
                    end_idx = min(len(self.main_buffer), self.speech_end_chunk_idx + cushion_chunks)
                    
                    speech_buffer = self.main_buffer[start_idx:end_idx]
                    self.logger.warning(f"   ✂️  VAD-trimmed buffer: {start_idx}:{end_idx} ({len(speech_buffer)} chunks, {len(speech_buffer)/self.chunks_per_second:.1f}s)")
                    utterance_data = np.concatenate(speech_buffer)
                else:
                    # Fallback: use entire buffer if VAD timing not available
                    self.logger.warning(f"   ⚠️  VAD timing unavailable, using entire buffer")
                    utterance_data = np.concatenate(self.main_buffer)
                    
                # Calculate duration based on actual data processed
                if self.speech_start_chunk_idx is not None and self.speech_end_chunk_idx is not None:
                    remaining_duration = len(speech_buffer) / self.chunks_per_second
                else:
                    remaining_duration = len(self.main_buffer) / self.chunks_per_second
                
                self.logger.warning(f"   📝 Processing final buffer segment ({remaining_duration:.1f}s)...")
                
                await self._send_status("processing", "Finalizing transcription...")

                # Use accumulated text as context for final segment
                accumulated_context = " ".join(final_text_parts)
                context_prompt = self.conversation_context + " " + accumulated_context
                
                self.logger.info(f"   🧠 Final context: '{context_prompt[:100]}...'")
                
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: self._transcribe_audio_with_vad_stats(utterance_data, context_prompt.strip()))

                # Check if task was cancelled during processing
                if asyncio.current_task().cancelled():
                    self.logger.debug("Final processing was cancelled due to interruption")
                    return

                if result["success"]:
                    final_segment_text = result["text"].strip()
                    if final_segment_text:
                        final_text_parts.append(final_segment_text)
                        self.logger.warning(f"   ✅ Final segment: '{final_segment_text[:60]}...'")
                    
            except asyncio.CancelledError:
                self.logger.debug("Final processing cancelled - graceful interruption handling")
                return
            except Exception as e:
                self.logger.exception(f"Error processing final buffer: {e}")
                # Continue with accumulated segments even if final buffer fails
                
        # Combine all text parts
        complete_text = " ".join(final_text_parts).strip()
        
        self.logger.warning(f"🏆 COMPLETE UTTERANCE ASSEMBLED:")
        self.logger.warning(f"   Length: {len(complete_text)} characters")
        self.logger.warning(f"   Parts: {len(final_text_parts)} segments")
        self.logger.warning(f"   Text: '{complete_text[:100]}...'")
        
        if complete_text:
            # Apply full text formatting to final result
            formatted_final = self._format_text_for_streaming(complete_text, is_partial=False)
            
            final_result = {
                "text": formatted_final,
                "is_partial": False,
                "status": "final",
                "success": True,
                "language": "auto",
                "duration": total_duration,
                "confidence": 0.95,
                "streaming_confidence": {
                    "final": 0.95
                },
                "utterance_info": {
                    "total_segments": len(self.accumulated_segments),
                    "had_final_buffer": len(self.main_buffer) > 0,
                    "total_duration": total_duration
                },
                "timestamp": time.time()
            }
            
            await self._send_transcription(final_result)
            
            # Update conversation context for future transcriptions
            self._update_conversation_context(formatted_final)
            
            self.logger.warning(f"✅ FINAL RESULT SENT: '{formatted_final[:100]}...'")
        else:
            self.logger.warning(f"⚠️  No text to send (empty utterance)")
            
        # Clean up
        self.is_processing = False
        self.final_processing_task = None
        self.accumulated_segments.clear()
        self.current_utterance_start_time = None
        self.segment_count = 0
        self.last_transcription = ""
        self.previous_partial_result = ""
        self.confirmed_text = ""
        
        await self._send_status("listening", "Ready for next utterance")

    async def _process_final_utterance(self) -> None:
        """Legacy method - now redirects to interruption-aware processing."""
        await self._process_final_utterance_with_interruption()

    async def _process_utterance(self) -> None:
        """Legacy method - now redirects to final utterance processing."""
        await self._process_final_utterance()

    def _transcribe_audio_with_vad_stats(self, audio_data: np.ndarray, prompt: str = "") -> Dict[str, Any]:
        """Transcribe audio data using Whisper with context and include VAD stats."""
        result = super()._transcribe_audio(audio_data, prompt)
        
        # Log VAD stats if available
        if result["success"] and self.vad:
            vad_stats = self.vad.get_stats()
            self.logger.debug(f"VAD stats: {vad_stats}")
        
        return result

    def _update_conversation_context(self, new_text: str):
        """Update conversation context buffer, keeping last ~200 words."""
        if not new_text.strip():
            return
            
        # Add new text to context
        self.conversation_context += " " + new_text.strip()
        
        # Keep only last 200 words to manage memory and prompt length
        words = self.conversation_context.split()
        if len(words) > 200:
            self.conversation_context = " ".join(words[-200:])
            
        self.logger.debug(f"Updated context: {len(self.conversation_context.split())} words")

    def _calculate_stable_prefix(self, previous_text: str, new_text: str) -> str:
        """Calculate stable prefix using advanced agreement scoring with difflib."""
        if not previous_text or not new_text:
            return ""
        
        # Use SequenceMatcher to find matching blocks
        matcher = difflib.SequenceMatcher(a=previous_text, b=new_text)
        matching_blocks = matcher.get_matching_blocks()
        
        # Find the longest matching block that starts at the beginning
        for block in matching_blocks:
            a_start, b_start, size = block
            
            # We want blocks that start at the beginning of both strings
            if a_start == 0 and b_start == 0 and size > 0:
                stable_prefix = previous_text[:size]
                self.logger.debug(f"Advanced agreement: '{stable_prefix}' (from '{previous_text[:20]}...' + '{new_text[:20]}...')")
                return stable_prefix
        
        # Fallback to simple commonprefix if no matching blocks found
        import os
        fallback = os.path.commonprefix([previous_text, new_text])
        self.logger.debug(f"Fallback to commonprefix: '{fallback}'")
        return fallback

    def _format_text_for_streaming(self, text: str, is_partial: bool = True) -> str:
        """Apply text formatting appropriate for streaming results."""
        if not self.text_formatter or not text.strip():
            return text
        
        try:
            if is_partial:
                # For partial results, only apply safe formatting that won't change significantly
                # Avoid formatting incomplete entities (numbers, dates, etc.)
                formatted = text
                
                # Only apply basic capitalization for partial results
                if hasattr(self.text_formatter, 'smart_capitalizer'):
                    # Apply minimal capitalization - just sentence starts
                    words = formatted.split()
                    if words:
                        words[0] = words[0].capitalize()
                        formatted = ' '.join(words)
                
                return formatted
            else:
                # For final results, apply full formatting
                return self.text_formatter.format_transcription(text)
                
        except Exception as e:
            self.logger.warning(f"Text formatting error: {e}")
            return text  # Return original text if formatting fails




    def _contains_exit_phrase(self, text: str) -> bool:
        """Check if text contains any exit phrases for wake word mode."""
        if not self.wake_word_callback:
            return False
            
        text_lower = text.lower().strip()
        for phrase in self.exit_phrases:
            if phrase.lower() in text_lower:
                return True
        return False

    async def _send_transcription(self, result: Dict[str, Any], extra: Optional[Dict] = None):
        """Enhanced transcription sender with exit phrase detection."""
        # Send the original transcription
        await super()._send_transcription(result, extra)
        
        # Check for exit phrases if we have a wake word callback
        if self.wake_word_callback:
            text = result.get("text", "").strip()
            if text and self._contains_exit_phrase(text):
                self.logger.info(f"👋 Exit phrase detected: '{text}' - triggering wake word callback")
                # Use asyncio.create_task to avoid blocking the transcription flow
                asyncio.create_task(self.wake_word_callback())

    async def _cleanup(self):
        """Clean up resources."""
        self.stop_event.set()

        # Cancel any ongoing processing tasks
        await self._cancel_partial_processing()
        
        if self.final_processing_task and not self.final_processing_task.done():
            self.logger.debug("Cancelling final processing task during cleanup")
            self.final_processing_task.cancel()
            try:
                await self.final_processing_task
            except asyncio.CancelledError:
                pass

        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)

        await super()._cleanup()
