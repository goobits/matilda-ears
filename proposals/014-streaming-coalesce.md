# Proposal 014: Streaming Request Coalescing

## Problem

Current streaming processes every chunk synchronously:
```
chunk1 → inference (2s) → result1
chunk2 → wait... → inference (2s) → result2
chunk3 → wait... → inference (2s) → result3
```

With 100ms chunks and 2s inference, we fall behind immediately.

## Solution

Coalesce requests with dirty-flag pattern:

```
chunk1 → inference starts
chunk2 → buffer, set dirty=true, return last_result
chunk3 → buffer, dirty already set, return last_result
         inference finishes, sees dirty → auto-restart
chunk4 → buffer, set dirty=true, return last_result
         inference finishes with chunks 1-4
```

Audio never lost. Inference runs on latest accumulated state.

## Tree Diff

```
matilda-ears/src/matilda_ears/transcription/streaming/
├── adapter.py
│   └── class StreamingAdapter
│       ├── __init__()
│       │   ├── + self._dirty = False
│       │   └── + self._inference_running = False
│       │
│       └── async process_chunk()
│           ├── - async with self._lock:
│           │       # Always runs inference
│           │
│           └── + # New implementation:
│               + self._buffer_chunk(pcm_int16)  # Always fast
│               + if self._inference_running:
│               +     self._dirty = True
│               +     return self._last_result
│               + return await self._run_inference_loop()
│
│       └── + async _run_inference_loop()
│           + while True:
│           +     self._dirty = False
│           +     self._inference_running = True
│           +     result = await self._do_inference()
│           +     self._inference_running = False
│           +     self._last_result = result
│           +     if not self._dirty:
│           +         return result
│           +     # More audio arrived, loop again
│
└── session.py
    └── (no changes - uses adapter interface)
```

## Implementation

```python
# adapter.py changes

class StreamingAdapter:
    def __init__(self, config=None):
        # ... existing ...
        self._dirty = False
        self._inference_running = False
        self._last_result = StreamingResult()
        self._pending_audio: list[np.ndarray] = []

    async def process_chunk(self, pcm_int16: np.ndarray) -> StreamingResult:
        """Non-blocking chunk processing with coalescing."""
        if not self._initialized:
            raise RuntimeError("Adapter not started")

        # Always accumulate audio (fast, never blocks)
        self._pending_audio.append(pcm_int16)
        self._total_samples += len(pcm_int16)

        # If inference running, just mark dirty and return last known
        if self._inference_running:
            self._dirty = True
            return self._last_result

        # Run inference loop (will keep running while dirty)
        return await self._run_inference_loop()

    async def _run_inference_loop(self) -> StreamingResult:
        """Run inference, re-running if new audio arrived."""
        while True:
            self._dirty = False
            self._inference_running = True

            try:
                # Flush pending audio to model
                async with self._lock:
                    for chunk in self._pending_audio:
                        audio_f32 = chunk.astype(np.float32) / 32768.0
                        self._wrapper.insert_audio_chunk(audio_f32)
                    self._pending_audio.clear()

                    # Run inference
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None, self._wrapper.process_iter
                    )

                alpha = result.get("alpha", "")
                if alpha:
                    self._alpha_text = (
                        f"{self._alpha_text} {alpha}".strip()
                        if self._alpha_text else alpha
                    )

                self._last_result = StreamingResult(
                    alpha_text=self._alpha_text,
                    omega_text=result.get("omega", ""),
                    audio_duration_seconds=self._total_samples / self.SAMPLE_RATE,
                )

            finally:
                self._inference_running = False

            # If no new audio arrived during inference, we're done
            if not self._dirty:
                return self._last_result
            # Otherwise loop to process newly arrived audio
```

## Behavior

| Scenario | Before | After |
|----------|--------|-------|
| Chunks during inference | Queue behind lock | Return cached, set dirty |
| Inference completes | Next in queue runs | Check dirty, re-run if needed |
| Fast hardware | Works fine | Works fine (no unnecessary skipping) |
| Slow hardware | Falls behind, OOM risk | Stays current, bounded memory |

## Client Impact

None. Same `partial_result` messages, just:
- More responsive (immediate return vs blocking)
- Results reflect latest audio state
- No message ordering changes

## Testing

```python
async def test_coalescing():
    adapter = StreamingAdapter()
    await adapter.start()

    # Simulate fast chunk arrival
    results = []
    for i in range(10):
        chunk = generate_audio_chunk(100)  # 100ms
        result = await adapter.process_chunk(chunk)
        results.append(result)

    # Should have some cached results (not all unique)
    # But final result should include all audio
    assert results[-1].audio_duration_seconds >= 1.0  # 10 * 100ms
```
