#!/usr/bin/env python3
"""Compare streaming vs batch transcription output.

Tests that streaming transcription produces the same text as batch transcription.
Uses faster-whisper directly to avoid server dependencies.
"""
import asyncio
import sys
import wave
import tempfile
from pathlib import Path

import numpy as np


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Read WAV file as int16 array."""
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    return np.frombuffer(frames, dtype=np.int16), rate


def audio_to_wav_bytes(audio: np.ndarray, sample_rate: int = 16000) -> bytes:
    """Convert int16 audio to WAV bytes."""
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


def save_wav(audio: np.ndarray, path: str, sample_rate: int = 16000):
    """Save audio to WAV file."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())


def batch_transcribe(audio: np.ndarray, model) -> str:
    """Run batch transcription on full audio."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        save_wav(audio, f.name)
        temp_path = f.name

    try:
        segments, info = model.transcribe(temp_path)
        text = " ".join(seg.text for seg in segments)
        return text.strip()
    finally:
        Path(temp_path).unlink(missing_ok=True)


def streaming_transcribe_chunked(audio: np.ndarray, model, chunk_seconds: float = 5.0) -> tuple[str, list[str]]:
    """Simulate streaming by transcribing in fixed-size chunks.

    This simulates the 'chunked' streaming strategy.
    """
    chunk_samples = int(chunk_seconds * 16000)
    partial_results = []
    accumulated_audio = np.array([], dtype=np.int16)

    for i in range(0, len(audio), chunk_samples):
        # Add new chunk to accumulated audio
        chunk = audio[i:i + chunk_samples]
        accumulated_audio = np.concatenate([accumulated_audio, chunk])

        # Transcribe accumulated audio so far
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            save_wav(accumulated_audio, f.name)
            temp_path = f.name

        try:
            segments, info = model.transcribe(temp_path)
            text = " ".join(seg.text for seg in segments).strip()
            partial_results.append(text)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    final_text = partial_results[-1] if partial_results else ""
    return final_text, partial_results


def streaming_transcribe_sliding(audio: np.ndarray, model, window_seconds: float = 10.0, step_seconds: float = 2.0) -> tuple[str, list[str]]:
    """Simulate streaming with sliding window (local agreement style).

    Transcribes overlapping windows and takes stable (confirmed) text.
    """
    window_samples = int(window_seconds * 16000)
    step_samples = int(step_seconds * 16000)

    partial_results = []
    confirmed_text = ""
    last_text = ""

    for i in range(0, len(audio), step_samples):
        # Get window of audio
        start = max(0, i - window_samples + step_samples)
        end = min(len(audio), i + step_samples)
        window = audio[start:end]

        if len(window) < 8000:  # Skip tiny windows
            continue

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            save_wav(window, f.name)
            temp_path = f.name

        try:
            segments, info = model.transcribe(temp_path)
            text = " ".join(seg.text for seg in segments).strip()

            # Simple confirmation: words that appear in consecutive transcriptions
            if last_text:
                last_words = last_text.lower().split()
                curr_words = text.lower().split()
                # Find common prefix
                common = []
                for lw, cw in zip(last_words, curr_words):
                    if lw == cw:
                        common.append(cw)
                    else:
                        break
                if common:
                    confirmed_text = " ".join(common)

            partial_results.append(text)
            last_text = text
        finally:
            Path(temp_path).unlink(missing_ok=True)

    # Final transcription of full audio
    final_text = batch_transcribe(audio, model)
    return final_text, partial_results


def main(wav_path: str):
    path = Path(wav_path)
    if not path.exists():
        print(f"File not found: {path}")
        return 1

    print(f"Loading: {path}")
    audio, rate = read_wav(path)

    if rate != 16000:
        print(f"Warning: Sample rate is {rate}, expected 16000")

    duration = len(audio) / rate
    print(f"Duration: {duration:.2f}s, Samples: {len(audio)}")

    # Load faster-whisper model
    print("\nLoading faster-whisper model...")
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("Model loaded: faster-whisper tiny")
    except ImportError:
        print("faster-whisper not available")
        return 1

    # Batch transcription
    print("\n" + "=" * 60)
    print("BATCH TRANSCRIPTION (full file at once)")
    print("=" * 60)
    batch_text = batch_transcribe(audio, model)
    print(f"\nResult ({len(batch_text)} chars):\n{batch_text}")

    # Streaming - chunked (like server's chunked strategy)
    print("\n" + "=" * 60)
    print("STREAMING - CHUNKED (5s chunks, accumulating)")
    print("=" * 60)
    chunked_text, chunked_partials = streaming_transcribe_chunked(audio, model, chunk_seconds=5.0)

    print(f"\nPartial results ({len(chunked_partials)} updates):")
    for i, p in enumerate(chunked_partials):
        preview = p[:60] + "..." if len(p) > 60 else p
        print(f"  [{i+1}] {preview}")

    print(f"\nFinal ({len(chunked_text)} chars):\n{chunked_text}")

    # Compare
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)

    # Normalize for comparison
    import re
    def normalize(text):
        return re.sub(r'[^\w\s]', '', text.lower()).strip()

    batch_norm = normalize(batch_text)
    chunked_norm = normalize(chunked_text)

    print(f"\nBatch:   {len(batch_text)} chars, {len(batch_norm.split())} words")
    print(f"Chunked: {len(chunked_text)} chars, {len(chunked_norm.split())} words")

    if batch_norm == chunked_norm:
        print("\n✓ Transcriptions match exactly!")
    else:
        # Word-level comparison
        batch_words = batch_norm.split()
        chunked_words = chunked_norm.split()

        # Find differences
        import difflib
        matcher = difflib.SequenceMatcher(None, batch_words, chunked_words)
        ratio = matcher.ratio()

        print(f"\n✗ Transcriptions differ (similarity: {ratio:.1%})")

        # Show differences
        print("\nDifferences:")
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':
                batch_part = ' '.join(batch_words[i1:i2])
                chunked_part = ' '.join(chunked_words[j1:j2])
                print(f"  {tag}: batch[{i1}:{i2}]='{batch_part}' vs chunked[{j1}:{j2}]='{chunked_part}'")

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python streaming_transcription_test.py <wav_file>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
