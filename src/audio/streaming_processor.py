#!/usr/bin/env python3
"""Real-time audio streaming processor using PyAudio
Replaces arecord with intelligent streaming audio capture
"""
import pyaudio
import numpy as np
import queue
import time
import logging
from typing import Optional, Callable

from src.config.stt_config import get_audio_config

class StreamingAudioProcessor:
    """Real-time audio streaming with intelligent buffering"""

    def __init__(self,
                 sample_rate: int = None,
                 channels: int = 1,
                 chunk_size: int = 1024,
                 audio_format=pyaudio.paInt16):

        audio_config = get_audio_config()
        self.sample_rate = sample_rate or audio_config.sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.audio_format = audio_format

        # Audio buffer management
        self.audio_buffer = queue.Queue()
        self.is_recording = False
        self.stream = None
        self.audio_thread = None

        # Complete audio accumulation
        self.accumulated_audio = []
        self.recording_start_time = None

        # Callbacks
        self.chunk_callback: Optional[Callable] = None

        # PyAudio instance
        self.pyaudio = pyaudio.PyAudio()

        logging.info(f"StreamingAudioProcessor initialized: {sample_rate}Hz, {channels}ch, {chunk_size} samples")

    def set_chunk_callback(self, callback: Callable[[np.ndarray, float], None]):
        """Set callback function called for each audio chunk"""
        self.chunk_callback = callback

    def start_recording(self):
        """Start real-time audio recording"""
        if self.is_recording:
            return

        self.is_recording = True
        self.accumulated_audio = []
        self.recording_start_time = time.time()

        # Open audio stream
        self.stream = self.pyaudio.open(
            format=self.audio_format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=self._audio_callback
        )

        self.stream.start_stream()
        logging.info("Real-time audio recording started")

    def stop_recording(self) -> np.ndarray:
        """Stop recording and return complete audio"""
        if not self.is_recording:
            return np.array([])

        self.is_recording = False

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

        # Return accumulated audio
        if self.accumulated_audio:
            complete_audio = np.concatenate(self.accumulated_audio)
            logging.info(f"Recording stopped: {len(complete_audio)} samples, {len(complete_audio)/self.sample_rate:.2f}s")
            return complete_audio
        return np.array([])

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for real-time audio processing"""
        if status:
            logging.warning(f"Audio callback status: {status}")

        # Convert bytes to numpy array
        audio_chunk = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32767.0

        # Store in accumulated audio
        self.accumulated_audio.append(audio_chunk.copy())

        # Calculate timestamp
        current_time = time.time()
        chunk_timestamp = current_time - self.recording_start_time if self.recording_start_time else 0.0

        # Call chunk callback if set
        if self.chunk_callback:
            try:
                self.chunk_callback(audio_chunk, chunk_timestamp)
            except Exception as e:
                logging.exception(f"Chunk callback error: {e}")

        return (None, pyaudio.paContinue)

    def get_recording_duration(self) -> float:
        """Get current recording duration in seconds"""
        if not self.recording_start_time:
            return 0.0
        return time.time() - self.recording_start_time

    def get_accumulated_audio(self) -> np.ndarray:
        """Get currently accumulated audio without stopping recording"""
        if self.accumulated_audio:
            return np.concatenate(self.accumulated_audio)
        return np.array([])

    def save_audio_to_file(self, audio_data: np.ndarray, filename: str):
        """Save audio data to WAV file for compatibility with existing server"""
        import wave

        # Convert float32 to int16
        audio_int16 = (audio_data * 32767).astype(np.int16)

        with wave.open(filename, "w") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

        logging.info(f"Audio saved to {filename}: {len(audio_data)} samples")

    def cleanup(self):
        """Clean up resources"""
        if self.is_recording:
            self.stop_recording()

        if self.pyaudio:
            self.pyaudio.terminate()

        logging.info("StreamingAudioProcessor cleaned up")

if __name__ == "__main__":
    # Test the streaming processor
    logging.basicConfig(level=logging.INFO)

    processor = StreamingAudioProcessor()

    def test_chunk_callback(chunk, timestamp):
        energy = np.mean(chunk ** 2)
        print(f"Chunk at {timestamp:.2f}s: energy={energy:.6f}")

    processor.set_chunk_callback(test_chunk_callback)

    print("Starting 5-second test recording...")
    processor.start_recording()
    time.sleep(5)
    audio = processor.stop_recording()

    print(f"Recorded {len(audio)} samples ({len(audio)/processor.sample_rate:.2f}s)")
    from src.config.stt_config import get_temp_dir
    temp_dir = get_temp_dir()
    processor.save_audio_to_file(audio, f"{temp_dir}/streaming_test.wav")

    processor.cleanup()
