import io
import wave
from types import SimpleNamespace

import numpy as np

from matilda_ears.transcription.server.internal.audio_utils import (
    TARGET_SAMPLE_RATE,
    decode_opus_chunk,
    downmix_to_mono,
    session_audio_to_wav,
)
from matilda_ears.transcription.server.internal.session_registry import PcmBuffer, ServerSession


def test_downmix_to_mono_averages_interleaved_channels() -> None:
    stereo = np.array([1000, -1000, 2000, 0], dtype=np.int16)

    assert downmix_to_mono(stereo, 2).tolist() == [0, 1000]


def test_decode_opus_chunk_normalizes_to_16khz_mono() -> None:
    stereo = np.tile(np.array([2000, 0], dtype=np.int16), 480)
    decoder = SimpleNamespace(sample_rate=48000, channels=2, decode_chunk=lambda _packet: stereo)

    samples = decode_opus_chunk(decoder, b"opus")

    assert samples.dtype == np.int16
    assert len(samples) == 160
    assert np.allclose(samples, 1000, atol=1)


def test_session_audio_to_wav_uses_normalized_pcm_shape() -> None:
    session = ServerSession("pcm", "client", "pcm")
    session.pcm = PcmBuffer(sample_rate=8000, channels=2, needs_resampling=True)
    session.pcm.append(np.full(TARGET_SAMPLE_RATE, 500, dtype=np.int16), TARGET_SAMPLE_RATE * 2)

    wav_data, duration = session_audio_to_wav(session) or (b"", 0.0)

    with wave.open(io.BytesIO(wav_data), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == TARGET_SAMPLE_RATE
        assert wav_file.getnframes() == TARGET_SAMPLE_RATE
    assert duration == 1.0
