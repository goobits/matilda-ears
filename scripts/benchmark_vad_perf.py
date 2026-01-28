#!/usr/bin/env python3
"""Benchmark VAD inference performance: Loop vs Batch."""

import time
import numpy as np
import torch
import sys
import os

# Ensure src is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from matilda_ears.audio.vad import SileroVAD

def benchmark():
    print("Initializing SileroVAD...")
    try:
        # Create VAD instance
        vad = SileroVAD(sample_rate=16000)
    except Exception as e:
        print(f"Failed to initialize VAD: {e}")
        return

    # Create dummy audio: 10 seconds of random noise
    duration_sec = 10
    sample_rate = 16000
    # Use float32 to simulate already converted audio or pass as is
    audio_data = np.random.uniform(-0.1, 0.1, size=duration_sec * sample_rate).astype(np.float32)

    required_size = 512

    # Define the inefficient loop method (patched onto the instance)
    def process_chunk_loop(self, audio_chunk: np.ndarray) -> float:
        # Reimplementation of the inefficient loop from the task description

        # Simulate the preprocessing in the actual method
        if audio_chunk.dtype == np.int16:
             audio_float = audio_chunk.astype(np.float32) / 32768.0
        else:
             audio_float = audio_chunk

        audio_float = audio_float.squeeze()

        if len(audio_float) > required_size:
            max_prob = 0.0
            # The inefficient loop
            for i in range(0, len(audio_float) - required_size + 1, required_size):
                sub_chunk = audio_float[i : i + required_size]
                audio_tensor = torch.from_numpy(sub_chunk)
                if self.model is None:
                    raise RuntimeError("Model not loaded")
                with torch.no_grad():
                    prob = self.model(audio_tensor, self.sample_rate).item()
                max_prob = max(max_prob, prob)
            return float(max_prob)
        return 0.0

    # Run Warmup
    print("Warming up...")
    vad.process_chunk(audio_data[:1024])

    # Measure Optimized (Current)
    print(f"Benchmarking Optimized Batch Processing (10s audio, {len(audio_data)} samples)...")
    start_time = time.time()
    iterations = 20
    for _ in range(iterations):
        # Current implementation in vad.py is already optimized
        vad.process_chunk(audio_data)
    end_time = time.time()
    avg_optimized = (end_time - start_time) / iterations
    print(f"Optimized Time: {avg_optimized:.4f}s per call")

    # Measure Inefficient Loop
    print(f"Benchmarking Inefficient Loop Processing (10s audio, {len(audio_data)} samples)...")

    # Bind the inefficient method
    import types
    vad.process_chunk_loop = types.MethodType(process_chunk_loop, vad)

    start_time = time.time()
    for _ in range(iterations):
        vad.process_chunk_loop(audio_data)
    end_time = time.time()
    avg_loop = (end_time - start_time) / iterations
    print(f"Inefficient Loop Time: {avg_loop:.4f}s per call")

    if avg_optimized > 0:
        speedup = avg_loop / avg_optimized
        print(f"Speedup: {speedup:.2f}x")
    else:
        print("Speedup: N/A (Optimized time is 0)")

if __name__ == "__main__":
    benchmark()
