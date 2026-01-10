import numpy as np
import pytest

from matilda_ears.transcription.streaming.config import StreamingConfig
from matilda_ears.transcription.streaming.internal.strategies.local_agreement import LocalAgreementStrategy


@pytest.mark.asyncio
async def test_local_agreement_confirmed_tentative_split():
    transcripts = [
        ["Hey", "Jarvis"],
        ["Hey", "Jarvis", "what's"],
        ["Hey", "Jarvis", "what's", "up"],
    ]
    call_count = 0

    async def fake_transcribe(_wav_bytes: bytes, _prompt: str):
        nonlocal call_count
        words = transcripts[min(call_count, len(transcripts) - 1)]
        call_count += 1
        info = {
            "words": [
                {
                    "word": word,
                    "start": idx * 0.2,
                    "end": (idx + 1) * 0.2,
                    "probability": 0.9,
                }
                for idx, word in enumerate(words)
            ]
        }
        return " ".join(words), info

    config = StreamingConfig(transcribe_interval_seconds=0.1, sample_rate=16000, max_buffer_seconds=2.0)
    strategy = LocalAgreementStrategy(fake_transcribe, config)

    chunk = np.zeros(config.transcribe_interval_samples, dtype=np.int16)

    results = []
    for _ in range(3):
        results.append(await strategy.process_audio(chunk))

    assert results[0].confirmed_text == ""
    assert results[0].tentative_text == "Hey Jarvis"
    assert results[1].confirmed_text == "Hey Jarvis"
    assert results[1].tentative_text == "what's"
    assert results[2].confirmed_text == "Hey Jarvis what's"
    assert results[2].tentative_text == "up"

    for prev, curr in zip(results, results[1:]):
        assert curr.confirmed_text.startswith(prev.confirmed_text)

    final = await strategy.finalize()
    assert final.is_final
    assert final.confirmed_text == "Hey Jarvis what's up"
    assert final.tentative_text == ""

    await strategy.cleanup()
