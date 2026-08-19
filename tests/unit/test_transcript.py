from dataclasses import FrozenInstanceError

import pytest

from matilda_ears.transcription.transcript import Transcript, TranscriptSegment


def test_transcript_is_an_immutable_structured_result():
    segment = TranscriptSegment(start=0.48, end=1.66, speaker="S01", text="Welcome everyone.")
    transcript = Transcript(
        text="Welcome everyone.",
        segments=(segment,),
        language="en",
        duration=1.66,
        backend="test",
    )

    assert transcript.segments == (segment,)
    with pytest.raises(FrozenInstanceError):
        transcript.text = "changed"
