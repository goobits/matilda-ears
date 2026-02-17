from matilda_ears import audio


def test_audio_public_api_is_explicit():
    # Keep this list small and stable. Everything else should live under internal modules.
    expected = {
        "OpusBatchDecoder",
        "OpusBatchEncoder",
        "OpusDecoder",
        "OpusEncoder",
        "OpusStreamDecoder",
        "PipeBasedAudioStreamer",
        "StreamingStats",
        "SileroVAD",
        "VADProbSmoother",
        "float32_to_int16",
        "int16_to_float32",
    }

    assert hasattr(audio, "__all__")
    assert expected.issubset(set(audio.__all__))

    for name in expected:
        assert hasattr(audio, name)
