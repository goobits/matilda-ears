#!/usr/bin/env python3
"""Test Opus streaming functionality."""

import wave
import tempfile
import os
import sys
import pytest

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from stt.audio.decoder import OpusDecoder, OpusStreamDecoder
from stt.transcription.client import OpusEncoder


def test_opus_encoder_decoder(preloaded_test_audio, preloaded_opus_codecs):
    """Test basic Opus encoding and decoding."""
    print("\n=== Testing Opus Encoder/Decoder ===")

    # Use preloaded test audio data
    audio_data = preloaded_test_audio
    codecs = preloaded_opus_codecs

    audio_int16 = audio_data["sine_440"]
    sample_rate = audio_data["sample_rate"]
    duration = audio_data["duration"]

    print(f"Using preloaded test audio: {len(audio_int16)} samples ({duration}s)")

    # Use preloaded codecs (create fresh instances to avoid state issues)
    encoder = OpusEncoder(sample_rate, 1)
    decoder = OpusDecoder(sample_rate, 1)

    # Process audio in chunks
    frame_size = 960  # 60ms at 16kHz
    chunks_processed = 0

    for i in range(0, len(audio_int16) - frame_size + 1, frame_size):
        chunk = audio_int16[i : i + frame_size]

        # Encode using our wrapper
        encoded = encoder.encode_chunk(chunk)

        if encoded:  # Our encoder may return None if buffering
            # Decode and accumulate
            samples_decoded = decoder.decode_chunk(encoded)
            chunks_processed += 1
            print(f"  Chunk {chunks_processed}: {len(encoded)} bytes Opus → {samples_decoded} samples PCM")

    # Flush any remaining data in encoder
    final_opus = encoder.flush()
    if final_opus:
        decoder.decode_chunk(final_opus)

    # Get final WAV
    wav_data = decoder.get_wav_data()
    print(f"\nFinal WAV: {len(wav_data)} bytes, {decoder.get_duration():.2f}s duration")

    # Verify by saving and checking
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav_data)
        temp_path = f.name

    # Read back and verify
    with wave.open(temp_path, "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == sample_rate
        frames = wav_file.getnframes()
        print(f"Verification: {frames} samples in WAV file")

    os.unlink(temp_path)
    print("✓ Opus encoding/decoding test passed!")


def test_stream_decoder_manager(preloaded_opus_codecs):
    """Test OpusStreamDecoder session management."""
    print("\n=== Testing Stream Decoder Manager ===")

    # Use preloaded codec configuration
    codecs = preloaded_opus_codecs
    manager = OpusStreamDecoder()

    # Create multiple sessions
    session1 = manager.create_session("client1_abc123")
    session2 = manager.create_session("client2_def456")

    print(f"Active sessions: {manager.get_active_sessions()}")

    # Test session operations
    assert manager.get_session("client1_abc123") == session1
    assert manager.get_session("client2_def456") == session2
    assert manager.get_session("nonexistent") is None

    # Remove session
    removed = manager.remove_session("client1_abc123")
    assert removed == session1
    assert len(manager.get_active_sessions()) == 1

    print("✓ Stream decoder manager test passed!")


def test_real_world_streaming(preloaded_test_audio, preloaded_opus_codecs):
    """Test realistic streaming scenario."""
    print("\n=== Testing Real-World Streaming Scenario ===")

    # Use preloaded test data
    audio_data = preloaded_test_audio
    codecs = preloaded_opus_codecs

    sample_rate = audio_data["sample_rate"]
    manager = OpusStreamDecoder()

    # Simulate client starting stream
    session_id = "test_stream_001"
    decoder = manager.create_session(session_id, sample_rate)

    # Simulate streaming audio chunks
    encoder = OpusEncoder(sample_rate, 1)  # Use our wrapper

    # Use preloaded speech-like audio (more realistic than generating)
    speech_audio = audio_data["speech_like"]
    frame_size = 960  # 60ms at 16kHz
    frames_sent = 0

    # Process speech audio in chunks
    for i in range(0, len(speech_audio) - frame_size + 1, frame_size):
        audio_chunk = speech_audio[i : i + frame_size]

        # Encode and "send" using our wrapper
        opus_data = encoder.encode_chunk(audio_chunk)

        if opus_data:  # Our encoder may return None if buffering
            # Decode on "server"
            decoder.decode_chunk(opus_data)
            frames_sent += 1

    print(f"Streamed {frames_sent} frames using preloaded speech-like audio")

    # End stream and get audio
    stats = decoder.get_stats()
    print(f"Stream stats: {stats}")

    wav_data = decoder.get_wav_data()
    print(f"Final audio: {len(wav_data)} bytes")

    # Clean up
    manager.remove_session(session_id)
    print("✓ Real-world streaming test passed!")


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])