from unittest.mock import Mock

from matilda_ears.audio.vad import SileroVAD


def test_reset_states_resets_model_and_local_state() -> None:
    vad = SileroVAD.__new__(SileroVAD)
    model = Mock()
    model.reset_states = Mock()
    vad.model = model
    vad.speech_timestamps = [{"start": 1, "end": 2}]
    vad.current_speech_start = 1
    vad.temp_end = 4
    vad.triggered = True

    vad.reset_states()

    model.reset_states.assert_called_once()
    assert vad.speech_timestamps == []
    assert vad.current_speech_start is None
    assert vad.temp_end == 0
    assert vad.triggered is False
