#!/home/miko/projects/stt-hotkey/venv/bin/python3
"""
Intelligent Voice Activity Detection (VAD) for pause-based streaming transcription
Combines energy-based detection with WebRTC VAD for maximum accuracy on clean audio
"""
import numpy as np
import webrtcvad
import logging
import time
from typing import List, Tuple, Optional
from collections import deque
from enum import Enum

class VoiceState(Enum):
    SILENCE = "silence"
    SPEECH = "speech"
    PAUSE = "pause"  # Speech pause (potential transcription trigger)

class IntelligentVAD:
    """Intelligent Voice Activity Detection with pause detection"""
    
    def __init__(self,
                 sample_rate: int = 44100,
                 frame_duration_ms: int = 30,  # WebRTC VAD frame duration
                 aggressiveness: int = 2,      # WebRTC VAD aggressiveness (0-3)
                 energy_threshold: float = 0.001,
                 pause_duration_ms: int = 1000,  # 1 second pause triggers transcription
                 min_speech_duration_ms: int = 300):  # Minimum speech before detecting pauses
        
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.aggressiveness = aggressiveness
        self.energy_threshold = energy_threshold
        self.pause_duration_ms = pause_duration_ms
        self.min_speech_duration_ms = min_speech_duration_ms
        
        # WebRTC VAD (works best with 8kHz, 16kHz, 32kHz, or 48kHz)
        self.webrtc_vad = webrtcvad.Vad(aggressiveness)
        self.webrtc_sample_rate = 16000  # Downsample to 16kHz for WebRTC
        
        # Frame processing
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        self.webrtc_frame_size = int(self.webrtc_sample_rate * frame_duration_ms / 1000)
        
        # State tracking
        self.current_state = VoiceState.SILENCE
        self.last_state_change = time.time()
        self.speech_start_time: Optional[float] = None
        self.last_speech_time: Optional[float] = None
        
        # History for smoothing decisions
        self.voice_history = deque(maxlen=10)  # Last 10 decisions
        self.energy_history = deque(maxlen=50)  # Energy smoothing
        
        # Statistics
        self.total_frames = 0
        self.speech_frames = 0
        self.pause_count = 0
        
        logging.info(f"IntelligentVAD initialized: {pause_duration_ms}ms pause threshold")
    
    def _downsample_for_webrtc(self, audio_chunk: np.ndarray) -> np.ndarray:
        """Downsample audio for WebRTC VAD compatibility"""
        if self.sample_rate == self.webrtc_sample_rate:
            return audio_chunk
        
        # Simple decimation (could use scipy.signal.resample for better quality)
        downsample_factor = self.sample_rate // self.webrtc_sample_rate
        return audio_chunk[::downsample_factor]
    
    def _calculate_energy(self, audio_chunk: np.ndarray) -> float:
        """Calculate RMS energy of audio chunk"""
        return np.sqrt(np.mean(audio_chunk ** 2))
    
    def _webrtc_vad_decision(self, audio_chunk: np.ndarray) -> bool:
        """Get WebRTC VAD decision"""
        try:
            # Downsample and convert to 16-bit PCM
            downsampled = self._downsample_for_webrtc(audio_chunk)
            
            # Ensure correct frame size
            if len(downsampled) < self.webrtc_frame_size:
                # Pad with zeros
                downsampled = np.pad(downsampled, (0, self.webrtc_frame_size - len(downsampled)))
            elif len(downsampled) > self.webrtc_frame_size:
                # Truncate
                downsampled = downsampled[:self.webrtc_frame_size]
            
            # Convert to 16-bit PCM bytes
            pcm_data = (downsampled * 32767).astype(np.int16).tobytes()
            
            # WebRTC VAD decision
            return self.webrtc_vad.is_speech(pcm_data, self.webrtc_sample_rate)
            
        except Exception as e:
            logging.warning(f"WebRTC VAD error: {e}")
            return False
    
    def process_chunk(self, audio_chunk: np.ndarray, timestamp: float) -> Tuple[VoiceState, bool]:
        """
        Process audio chunk and return (current_state, should_transcribe)
        
        Returns:
            current_state: Current voice activity state
            should_transcribe: True if accumulated audio should be transcribed now
        """
        self.total_frames += 1
        current_time = time.time()
        
        # Calculate energy
        energy = self._calculate_energy(audio_chunk)
        self.energy_history.append(energy)
        
        # Get WebRTC VAD decision
        webrtc_speech = self._webrtc_vad_decision(audio_chunk)
        
        # Combined decision: energy + WebRTC
        energy_speech = energy > self.energy_threshold
        speech_detected = webrtc_speech and energy_speech
        
        # Add to history for smoothing
        self.voice_history.append(speech_detected)
        
        # Smooth decision: majority vote from recent history
        recent_speech_ratio = sum(self.voice_history) / len(self.voice_history)
        smoothed_speech = recent_speech_ratio > 0.5
        
        # State machine
        previous_state = self.current_state
        should_transcribe = False
        
        if smoothed_speech:
            # Speech detected
            self.speech_frames += 1
            self.last_speech_time = current_time
            
            if self.current_state == VoiceState.SILENCE:
                # Transition: Silence -> Speech
                self.current_state = VoiceState.SPEECH
                self.speech_start_time = current_time
                self.last_state_change = current_time
                logging.debug(f"Speech started at {timestamp:.2f}s")
                
            elif self.current_state == VoiceState.PAUSE:
                # Transition: Pause -> Speech (resume speaking)
                self.current_state = VoiceState.SPEECH
                self.last_state_change = current_time
                logging.debug(f"Speech resumed at {timestamp:.2f}s")
        
        else:
            # No speech detected
            if self.current_state == VoiceState.SPEECH:
                # Potential pause - check duration
                time_since_speech = current_time - (self.last_speech_time or current_time)
                
                if time_since_speech * 1000 >= self.pause_duration_ms:
                    # Long enough pause detected
                    speech_duration = (self.last_speech_time or current_time) - (self.speech_start_time or current_time)
                    
                    if speech_duration * 1000 >= self.min_speech_duration_ms:
                        # We had enough speech, trigger transcription
                        self.current_state = VoiceState.PAUSE
                        self.last_state_change = current_time
                        self.pause_count += 1
                        should_transcribe = True
                        
                        logging.info(f"Pause detected at {timestamp:.2f}s after {speech_duration:.2f}s speech - triggering transcription")
                    else:
                        # Too short speech, go back to silence
                        self.current_state = VoiceState.SILENCE
                        self.last_state_change = current_time
                        logging.debug(f"Short speech ({speech_duration:.2f}s) ended, back to silence")
            
            elif self.current_state == VoiceState.PAUSE:
                # Stay in pause state until next speech or timeout
                time_in_pause = current_time - self.last_state_change
                if time_in_pause > 5.0:  # 5 second timeout
                    self.current_state = VoiceState.SILENCE
                    self.last_state_change = current_time
                    logging.debug("Pause timeout, returning to silence")
        
        return self.current_state, should_transcribe
    
    def get_statistics(self) -> dict:
        """Get VAD performance statistics"""
        speech_ratio = self.speech_frames / max(1, self.total_frames)
        avg_energy = np.mean(self.energy_history) if self.energy_history else 0
        
        return {
            'total_frames': self.total_frames,
            'speech_frames': self.speech_frames,
            'speech_ratio': speech_ratio,
            'pause_count': self.pause_count,
            'current_state': self.current_state.value,
            'avg_energy': avg_energy,
            'energy_threshold': self.energy_threshold
        }
    
    def reset(self):
        """Reset VAD state for new recording session"""
        self.current_state = VoiceState.SILENCE
        self.last_state_change = time.time()
        self.speech_start_time = None
        self.last_speech_time = None
        self.voice_history.clear()
        self.energy_history.clear()
        self.total_frames = 0
        self.speech_frames = 0
        self.pause_count = 0
        
        logging.info("VAD state reset for new session")
    
    def adjust_sensitivity(self, energy_threshold: Optional[float] = None, 
                          pause_duration_ms: Optional[int] = None):
        """Dynamically adjust VAD sensitivity"""
        if energy_threshold is not None:
            self.energy_threshold = energy_threshold
            logging.info(f"Energy threshold adjusted to {energy_threshold}")
        
        if pause_duration_ms is not None:
            self.pause_duration_ms = pause_duration_ms
            logging.info(f"Pause duration adjusted to {pause_duration_ms}ms")

if __name__ == "__main__":
    # Test the VAD detector
    logging.basicConfig(level=logging.INFO)
    
    # Create test audio with speech and pauses
    sample_rate = 44100
    duration = 10.0  # 10 seconds
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Simulate speech with pauses
    test_audio = np.zeros_like(t)
    
    # Add "speech" segments (sine waves)
    speech_segments = [(1, 3), (5, 7), (8.5, 9.5)]  # Start, end times
    for start, end in speech_segments:
        mask = (t >= start) & (t <= end)
        test_audio[mask] = 0.3 * np.sin(2 * np.pi * 440 * t[mask])  # 440 Hz
    
    # Add some noise
    test_audio += 0.05 * np.random.randn(len(test_audio))
    
    print(f"Testing VAD with {len(test_audio)} samples...")
    
    # Initialize VAD
    vad = IntelligentVAD(sample_rate=sample_rate, pause_duration_ms=500)
    
    # Process in chunks
    chunk_size = 1024
    transcription_triggers = []
    
    for i in range(0, len(test_audio), chunk_size):
        chunk = test_audio[i:i + chunk_size]
        timestamp = i / sample_rate
        
        if len(chunk) < chunk_size:
            chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
        
        state, should_transcribe = vad.process_chunk(chunk, timestamp)
        
        if should_transcribe:
            transcription_triggers.append(timestamp)
            print(f"TRANSCRIPTION TRIGGER at {timestamp:.2f}s")
    
    # Show results
    stats = vad.get_statistics()
    print("\\nVAD Statistics:")
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    print(f"\\nTranscription triggers: {transcription_triggers}")
    print("Expected triggers after speech segments ending at: 3s, 7s, 9.5s")