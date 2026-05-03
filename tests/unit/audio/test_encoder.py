import numpy as np

from matilda_ears.audio.encoder import OpusEncoder


def test_encode_chunks_emits_all_complete_frames_without_buffer_growth():
    encoder = OpusEncoder(sample_rate=16000, channels=1)
    audio = np.zeros(encoder.frame_size * 3, dtype=np.int16)

    packets = encoder.encode_chunks(audio)

    assert len(packets) == 3
    assert encoder.buffer_size == 0
    assert encoder.audio_buffer == []


def test_encode_chunk_keeps_legacy_single_packet_behavior():
    encoder = OpusEncoder(sample_rate=16000, channels=1)
    audio = np.zeros(encoder.frame_size * 2, dtype=np.int16)

    packet = encoder.encode_chunk(audio)

    assert packet is not None
    assert encoder.buffer_size == encoder.frame_size
