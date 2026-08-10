from unittest.mock import Mock

import numpy as np

from matilda_ears.wake_word.backends.openwakeword import OpenWakeWordBackend


def _backend_with_predictions(predictions: dict[str, float]) -> OpenWakeWordBackend:
    backend = OpenWakeWordBackend.__new__(OpenWakeWordBackend)
    backend.threshold = 0.5
    backend._phrase_to_agent = {"hey_matilda": "Matilda"}
    backend.model = Mock(predict=Mock(return_value=predictions))
    return backend


def test_openwakeword_evaluate_returns_detection_and_score_from_one_prediction() -> None:
    backend = _backend_with_predictions({"hey_matilda": 0.9, "noise": 0.1})

    detection, phrase, confidence = backend.evaluate(np.zeros(1280, dtype=np.int16))

    assert detection == ("Matilda", "hey_matilda", 0.9)
    assert phrase == "hey_matilda"
    assert confidence == 0.9
    backend.model.predict.assert_called_once()


def test_openwakeword_evaluate_preserves_below_threshold_debug_score() -> None:
    backend = _backend_with_predictions({"hey_matilda": 0.3})

    detection, phrase, confidence = backend.evaluate(np.zeros(1280, dtype=np.int16))

    assert detection is None
    assert phrase == "hey_matilda"
    assert confidence == 0.3
