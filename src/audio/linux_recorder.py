"""Audio recording functionality.
"""

import os
import subprocess
import time
import wave
import logging
import sys
import os
# Add project root to path if not already there
if os.path.join(os.path.dirname(__file__), '..', '..') not in sys.path:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from src.config.stt_config import config

logger = logging.getLogger(__name__)

class AudioRecorder:
    """Handles audio recording using arecord."""

    def __init__(self):
        self.recording_process = None
        self.output_file = None
        self.cancel_file = None

    def start_recording(self, filename_prefix="audio_recording"):
        """Start audio recording to a temporary file."""
        # Generate unique filenames
        timestamp = str(int(time.time() * 1000))
        self.output_file = os.path.join(config.temp_dir, f"{filename_prefix}_{timestamp}.wav")
        self.cancel_file = os.path.join(config.temp_dir, f"cancel_{timestamp}.txt")

        # Clean up any stale cancel files
        self._cleanup_cancel_files()

        try:
            # Start arecord process
            self.recording_process = subprocess.Popen([
                "arecord",
                "-f", config.audio_format,
                "-r", str(config.audio_sample_rate),
                "-c", str(config.audio_channels),
                self.output_file
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            logger.info(f"Started recording to: {self.output_file}")
            return self.output_file, self.cancel_file

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return None, None

    def stop_recording(self):
        """Stop the current recording and return the audio file path."""
        if not self.recording_process:
            return None

        try:
            # Terminate the recording process
            self.recording_process.terminate()
            self.recording_process.wait(timeout=5)

            # Brief delay to ensure file is written
            time.sleep(config.record_stop_delay)

            # Verify the file exists and has content
            if os.path.exists(self.output_file) and os.path.getsize(self.output_file) > 0:
                logger.info(f"Recording stopped: {self.output_file}")
                return self.output_file
            logger.warning("Recording file is empty or doesn't exist")
            return None

        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")
            return None
        finally:
            self.recording_process = None

    def cancel_recording(self):
        """Cancel the current recording."""
        if self.cancel_file:
            try:
                with open(self.cancel_file, "w") as f:
                    f.write("cancelled")
                logger.info("Recording cancelled")
            except Exception as e:
                logger.error(f"Failed to create cancel file: {e}")

        if self.recording_process:
            try:
                self.recording_process.terminate()
                self.recording_process.wait(timeout=5)
            except Exception as e:
                logger.error(f"Failed to terminate recording process: {e}")
            finally:
                self.recording_process = None

        # Clean up output file
        if self.output_file and os.path.exists(self.output_file):
            try:
                os.remove(self.output_file)
            except Exception as e:
                logger.error(f"Failed to remove recording file: {e}")

    def get_audio_duration(self, audio_file):
        """Get the duration of an audio file in seconds."""
        try:
            with wave.open(audio_file, "rb") as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                duration = frames / float(sample_rate)
                return duration
        except Exception as e:
            logger.error(f"Failed to get audio duration: {e}")
            return None

    def _cleanup_cancel_files(self):
        """Clean up old cancel files to prevent conflicts."""
        try:
            cancel_files = [f for f in os.listdir(config.temp_dir) if f.startswith("cancel_")]
            for cancel_file in cancel_files:
                os.remove(os.path.join(config.temp_dir, cancel_file))
        except Exception as e:
            logger.warning(f"Failed to cleanup cancel files: {e}")

    def is_recording(self):
        """Check if currently recording."""
        return self.recording_process is not None and self.recording_process.poll() is None
