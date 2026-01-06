"""Opus batch encoder/decoder for compressing audio files."""

import io
import wave
import numpy as np
import opuslib
from typing import Tuple

# Setup standardized logging
try:
    from ...core.config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class OpusBatchEncoder:
    """Encode entire WAV files to Opus format for reduced network transfer."""

    def __init__(self, bitrate: int = 24000):
        """Initialize Opus batch encoder.

        Args:
            bitrate: Opus bitrate in bits per second (default: 24000)

        """
        self.bitrate = bitrate
        self.frame_size = 960  # 60ms at 16kHz
        logger.info(f"OpusBatchEncoder initialized with bitrate: {bitrate}bps")

    def encode_wav_to_opus(self, wav_data: bytes) -> Tuple[bytes, dict]:
        """Encode WAV file data to Opus format.

        Args:
            wav_data: Complete WAV file as bytes

        Returns:
            (opus_data, metadata) where metadata contains audio info

        """
        # Parse WAV file
        wav_buffer = io.BytesIO(wav_data)
        with wave.open(wav_buffer, "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_rate = wav_file.getframerate()
            sample_width = wav_file.getsampwidth()
            n_frames = wav_file.getnframes()
            pcm_data = wav_file.readframes(n_frames)

        # Convert to numpy array
        if sample_width == 2:
            audio_array = np.frombuffer(pcm_data, dtype=np.int16)
        else:
            raise ValueError(f"Unsupported sample width: {sample_width}")

        # Create Opus encoder
        encoder = opuslib.Encoder(sample_rate, channels, opuslib.APPLICATION_AUDIO)
        # Note: Setting bitrate causes 'invalid argument' error in opuslib
        # encoder.bitrate = self.bitrate  # Commented out - use default bitrate

        # Encode in chunks and track frame sizes
        opus_chunks = []
        frame_sizes = []
        total_samples = len(audio_array)
        samples_per_frame = self.frame_size * channels

        for i in range(0, total_samples, samples_per_frame):
            # Get frame (pad last frame if needed)
            end = min(i + samples_per_frame, total_samples)
            frame = audio_array[i:end]

            if len(frame) < samples_per_frame:
                # Pad last frame
                padding = np.zeros(samples_per_frame - len(frame), dtype=np.int16)
                frame = np.concatenate([frame, padding])

            # Encode frame
            try:
                encoded = encoder.encode(frame.tobytes(), self.frame_size)
                opus_chunks.append(encoded)
                frame_sizes.append(len(encoded))  # Track frame size for decoding
            except Exception as e:
                logger.error(f"Opus encoding error on frame {i//samples_per_frame}: {e}")
                raise

        # Combine all chunks
        opus_data = b"".join(opus_chunks)

        # Create metadata
        metadata = {
            "channels": channels,
            "sample_rate": sample_rate,
            "frame_size": self.frame_size,
            "total_frames": len(opus_chunks),
            "frame_sizes": frame_sizes,  # Track individual frame sizes for decoding
            "original_samples": total_samples,
            "original_size": len(wav_data),
            "opus_size": len(opus_data),
            "compression_ratio": len(wav_data) / len(opus_data),
        }

        logger.info(
            f"Encoded WAV to Opus: {len(wav_data)} → {len(opus_data)} bytes "
            f"({metadata['compression_ratio']:.1f}x compression)"
        )

        return opus_data, metadata


class OpusBatchDecoder:
    """Decode Opus data back to WAV format."""

    def decode_opus_to_wav(self, opus_data: bytes, metadata: dict) -> bytes:
        """Decode Opus data to WAV format using the frame information from metadata.

        Args:
            opus_data: Opus encoded audio (concatenated frames)
            metadata: Audio metadata including frame_sizes list

        Returns:
            WAV file data as bytes

        """
        channels = metadata["channels"]
        sample_rate = metadata["sample_rate"]
        frame_size = metadata["frame_size"]
        frame_sizes = metadata.get("frame_sizes", [])
        original_samples = metadata["original_samples"]

        if not frame_sizes:
            # Fallback: try to decode as single frame
            logger.warning("No frame sizes in metadata, attempting single-frame decode")
            try:
                decoder = opuslib.Decoder(sample_rate, channels)
                pcm_data = decoder.decode(opus_data, frame_size * metadata.get("total_frames", 1))
                audio_array = np.frombuffer(pcm_data, dtype=np.int16)[:original_samples]
            except Exception as e:
                logger.error(f"Single-frame Opus decode failed: {e}")
                raise
        else:
            # Decode frame by frame using exact frame sizes
            decoder = opuslib.Decoder(sample_rate, channels)
            pcm_chunks = []
            offset = 0

            for i, frame_length in enumerate(frame_sizes):
                if offset + frame_length > len(opus_data):
                    logger.warning(f"Frame {i} extends beyond data: {offset + frame_length} > {len(opus_data)}")
                    break

                frame_data = opus_data[offset : offset + frame_length]
                try:
                    pcm_data = decoder.decode(frame_data, frame_size)
                    pcm_chunks.append(pcm_data)
                    offset += frame_length
                except Exception as e:
                    logger.error(f"Opus decoding error on frame {i} (size {frame_length}): {e}")
                    # Continue with next frame
                    offset += frame_length

            # Combine PCM data and trim to original length
            if pcm_chunks:
                pcm_data = b"".join(pcm_chunks)
                audio_array = np.frombuffer(pcm_data, dtype=np.int16)
                audio_array = audio_array[:original_samples]
            else:
                logger.error("No frames successfully decoded")
                raise ValueError("Failed to decode any Opus frames")

        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_array.tobytes())

        wav_buffer.seek(0)
        wav_data = wav_buffer.read()

        logger.info(f"Decoded Opus to WAV: {len(opus_data)} → {len(wav_data)} bytes")

        return wav_data
