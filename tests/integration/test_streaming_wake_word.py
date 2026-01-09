#!/usr/bin/env python3
"""Test streaming wake word detection vs offline baseline.

Simulates the full server-side streaming pipeline:
1. Chunk WAV into client-sized pieces (1600 samples)
2. Encode to Opus (like client)
3. Decode from Opus (like server)
4. Run through wake word detector (like server's _process_wake_word_chunk)
5. Compare with offline detection
"""
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path("/workspace/matilda-ears/src")))

from matilda_ears.wake_word.detector import WakeWordDetector


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Read WAV file as int16 array."""
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    return np.frombuffer(frames, dtype=np.int16), rate


def offline_detection(audio: np.ndarray, detector: WakeWordDetector) -> list[tuple[float, float, str]]:
    """Run offline detection - process all audio with fresh detector state."""
    detector.reset()
    detections = []
    chunk_size = 1280  # 80ms @ 16kHz

    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i + chunk_size]
        if len(chunk) < chunk_size:
            chunk = np.pad(chunk, (0, chunk_size - len(chunk)))

        phrase, score = detector.best_score(chunk)
        t = i / 16000
        if score > 0.1:  # Log anything notable
            detections.append((t, score, phrase or ""))

    return detections


def streaming_detection_no_opus(audio: np.ndarray, detector: WakeWordDetector) -> list[tuple[float, float, str]]:
    """Simulate streaming without Opus - just different chunk sizes."""
    detector.reset()
    detections = []

    # Client sends 1600-sample chunks (~100ms)
    client_chunk_size = 1600
    # Server processes in 1280-sample frames (80ms) for wake word
    ww_frame_size = 1280

    # Simulate server's wake word buffer
    ww_buffer = np.array([], dtype=np.int16)

    for i in range(0, len(audio), client_chunk_size):
        # Simulate client chunk
        client_chunk = audio[i:i + client_chunk_size]

        # Server receives and adds to wake word buffer (like _process_wake_word_chunk)
        ww_buffer = np.concatenate([ww_buffer, client_chunk])

        # Process complete 1280-sample frames
        offset = 0
        while offset + ww_frame_size <= len(ww_buffer):
            frame = ww_buffer[offset:offset + ww_frame_size]
            phrase, score = detector.best_score(frame)
            t = (i + offset) / 16000
            if score > 0.1:
                detections.append((t, score, phrase or ""))
            offset += ww_frame_size

        # Keep remainder in buffer
        ww_buffer = ww_buffer[offset:]

    return detections


def streaming_detection_with_opus(audio: np.ndarray, detector: WakeWordDetector) -> list[tuple[float, float, str]]:
    """Simulate streaming WITH Opus encode/decode."""
    try:
        import opuslib
    except ImportError:
        print("opuslib not available, skipping Opus test")
        return []

    detector.reset()
    detections = []

    # Opus encoder/decoder setup
    encoder = opuslib.Encoder(16000, 1, opuslib.APPLICATION_VOIP)
    decoder = opuslib.Decoder(16000, 1)

    # Client sends 960-sample Opus frames (60ms)
    opus_frame_size = 960
    # Server processes in 1280-sample frames for wake word
    ww_frame_size = 1280

    # Simulate server's wake word buffer
    ww_buffer = np.array([], dtype=np.int16)

    sample_idx = 0
    for i in range(0, len(audio), opus_frame_size):
        # Client: get PCM frame
        pcm_frame = audio[i:i + opus_frame_size]
        if len(pcm_frame) < opus_frame_size:
            pcm_frame = np.pad(pcm_frame, (0, opus_frame_size - len(pcm_frame)))

        # Client: encode to Opus
        opus_data = encoder.encode(pcm_frame.tobytes(), opus_frame_size)

        # Server: decode from Opus
        decoded_bytes = decoder.decode(opus_data, opus_frame_size)
        decoded_pcm = np.frombuffer(decoded_bytes, dtype=np.int16)

        # Server: add to wake word buffer
        ww_buffer = np.concatenate([ww_buffer, decoded_pcm])

        # Process complete 1280-sample frames
        offset = 0
        while offset + ww_frame_size <= len(ww_buffer):
            frame = ww_buffer[offset:offset + ww_frame_size]
            phrase, score = detector.best_score(frame)
            t = sample_idx / 16000
            if score > 0.1:
                detections.append((t, score, phrase or ""))
            offset += ww_frame_size
            sample_idx += ww_frame_size

        # Keep remainder in buffer
        ww_buffer = ww_buffer[offset:]

    return detections


def find_peaks(detections: list[tuple[float, float, str]], threshold: float = 0.2) -> list[tuple[float, float]]:
    """Find peak detections above threshold, grouped by time proximity."""
    if not detections:
        return []

    peaks = []
    current_peak = None

    for t, score, phrase in detections:
        if score >= threshold:
            if current_peak is None:
                current_peak = (t, score)
            elif t - current_peak[0] < 0.5:  # Within 500ms, update if higher
                if score > current_peak[1]:
                    current_peak = (t, score)
            else:
                peaks.append(current_peak)
                current_peak = (t, score)

    if current_peak:
        peaks.append(current_peak)

    return peaks


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

    # Create detector
    detector = WakeWordDetector.from_config({
        "threshold": 0.2,
        "noise_suppression": False,
        "agent_aliases": [{"agent": "Matilda", "aliases": ["hey_jarvis"]}]
    })

    print("\n" + "=" * 60)
    print("OFFLINE DETECTION (baseline)")
    print("=" * 60)
    offline = offline_detection(audio, detector)
    offline_peaks = find_peaks(offline)
    print(f"Peaks found: {len(offline_peaks)}")
    for t, score in offline_peaks:
        print(f"  {t:.2f}s: {score:.4f}")

    print("\n" + "=" * 60)
    print("STREAMING (no Opus) - chunked like client")
    print("=" * 60)
    streaming_no_opus = streaming_detection_no_opus(audio, detector)
    streaming_peaks = find_peaks(streaming_no_opus)
    print(f"Peaks found: {len(streaming_peaks)}")
    for t, score in streaming_peaks:
        print(f"  {t:.2f}s: {score:.4f}")

    print("\n" + "=" * 60)
    print("STREAMING (with Opus) - full pipeline")
    print("=" * 60)
    streaming_opus = streaming_detection_with_opus(audio, detector)
    if streaming_opus:
        opus_peaks = find_peaks(streaming_opus)
        print(f"Peaks found: {len(opus_peaks)}")
        for t, score in opus_peaks:
            print(f"  {t:.2f}s: {score:.4f}")

    # Compare
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)
    print(f"Offline detections:       {len(offline_peaks)}")
    print(f"Streaming (no Opus):      {len(streaming_peaks)}")
    if streaming_opus:
        print(f"Streaming (with Opus):    {len(opus_peaks)}")

    if len(offline_peaks) == len(streaming_peaks):
        print("\n✓ Streaming matches offline!")
    else:
        print(f"\n✗ Mismatch: offline={len(offline_peaks)}, streaming={len(streaming_peaks)}")

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python streaming_vs_offline_test.py <wav_file>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
