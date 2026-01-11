# Proposal 015: CPU-Optimized Streaming Stack

## Goal

Get streaming to "A" grade on CPU by combining three optimizations:
1. VAD gating (skip silence) - **reuse existing `audio/vad.py`**
2. Request coalescing (don't block)
3. Faster model (tiny/base)

Combined effect: ~20-50x effective speedup on CPU.

## Current State

```
Audio → [all chunks] → SimulStreaming (whisper-small) → 2s inference
```

- Processes silence: ~60% wasted
- Blocks on inference: queue backup
- whisper-small: 244M params, slow on CPU

## Target State

```
Audio → VAD → [speech only] → Coalescing → whisper-tiny → <200ms
        ↓ silence
      Skip (return empty)
```

## Tree Diff

```
matilda-ears/src/matilda_ears/transcription/
├── streaming/
│   ├── adapter.py
│   │   ├── StreamingConfig
│   │   │   ├── ~ model_size: str = "tiny"  # was "small"
│   │   │   ├── + vad_enabled: bool = True
│   │   │   └── + vad_threshold: float = 0.5
│   │   │
│   │   └── class StreamingAdapter
│   │       ├── __init__()
│   │       │   ├── + self._vad: SileroVAD | None = None
│   │       │   ├── + self._dirty = False
│   │       │   ├── + self._inference_running = False
│   │       │   └── + self._pending_audio: list = []
│   │       │
│   │       ├── async start()
│   │       │   └── + if config.vad_enabled:
│   │       │       +     from matilda_ears.audio.vad import SileroVAD  # REUSE
│   │       │       +     self._vad = SileroVAD(threshold=config.vad_threshold)
│   │       │
│   │       ├── async process_chunk()
│   │       │   └── # Rewrite: VAD gate + coalescing
│   │       │       + if self._vad:
│   │       │       +     prob = self._vad.process_chunk(chunk)
│   │       │       +     if prob < self._vad.threshold:
│   │       │       +         return self._last_result  # Skip silence
│   │       │       + self._pending_audio.append(chunk)
│   │       │       + if self._inference_running:
│   │       │       +     self._dirty = True
│   │       │       +     return self._last_result
│   │       │       + return await self._run_inference_loop()
│   │       │
│   │       └── + async _run_inference_loop()
│   │           + # Coalescing loop (see proposal 014)
│   │
│   └── (no new files - reuse audio/vad.py)
│
└── server/
    └── stream_handlers.py
        └── _create_streaming_session()
            └── ~ config = StreamingConfig(model_size="tiny", vad_enabled=True)
```

## Existing VAD (REUSE - no new code)

```python
# Already exists: matilda_ears/audio/vad.py
from matilda_ears.audio.vad import SileroVAD

vad = SileroVAD(threshold=0.5)
prob = vad.process_chunk(pcm_int16)  # Returns 0.0-1.0
is_speech = prob > vad.threshold
vad.reset_states()  # Between sessions
```

## Adapter Changes

```python
# adapter.py - key changes only

@dataclass
class StreamingConfig:
    model_size: str = "tiny"  # Changed from "small"
    vad_enabled: bool = True
    vad_threshold: float = 0.5
    # ... rest unchanged

class StreamingAdapter:
    def __init__(self, config=None):
        self.config = config or StreamingConfig()
        self._vad = None  # SileroVAD from audio/vad.py
        self._dirty = False
        self._inference_running = False
        self._last_result = StreamingResult()
        self._pending_audio: list[np.ndarray] = []
        # ... rest unchanged

    async def start(self):
        # ... existing model init ...

        if self.config.vad_enabled:
            from matilda_ears.audio.vad import SileroVAD  # REUSE existing
            self._vad = SileroVAD(threshold=self.config.vad_threshold)

    async def process_chunk(self, pcm_int16: np.ndarray) -> StreamingResult:
        if not self._initialized:
            raise RuntimeError("Adapter not started")

        self._total_samples += len(pcm_int16)

        # 1. VAD gate - skip silence (uses existing SileroVAD)
        if self._vad:
            speech_prob = self._vad.process_chunk(pcm_int16)
            if speech_prob < self._vad.threshold:
                return self._last_result

        # 2. Buffer audio
        self._pending_audio.append(pcm_int16)

        # 3. Coalesce - skip if busy
        if self._inference_running:
            self._dirty = True
            return self._last_result

        # 4. Run inference
        return await self._run_inference_loop()

    async def _run_inference_loop(self) -> StreamingResult:
        while True:
            self._dirty = False
            self._inference_running = True

            try:
                async with self._lock:
                    for chunk in self._pending_audio:
                        audio_f32 = chunk.astype(np.float32) / 32768.0
                        self._wrapper.insert_audio_chunk(audio_f32)
                    self._pending_audio.clear()

                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        None, self._wrapper.process_iter
                    )

                alpha = result.get("alpha", "")
                if alpha:
                    self._alpha_text = f"{self._alpha_text} {alpha}".strip() if self._alpha_text else alpha

                self._last_result = StreamingResult(
                    alpha_text=self._alpha_text,
                    omega_text=result.get("omega", ""),
                    audio_duration_seconds=self._total_samples / self.SAMPLE_RATE,
                )
            finally:
                self._inference_running = False

            if not self._dirty:
                return self._last_result
```

## Expected Performance

| Metric | Before | After | Speedup |
|--------|--------|-------|---------|
| Model params | 244M (small) | 39M (tiny) | ~6x |
| Silence processing | 100% | ~0% | ~2-3x |
| Blocked requests | Queue | Return cached | Responsive |
| **Effective inference** | ~2000ms | ~200-400ms | ~5-10x |

## Tradeoffs

| | whisper-tiny | whisper-small |
|--|--------------|---------------|
| Speed | ~6x faster | Baseline |
| WER (accuracy) | ~7% | ~4% |
| Good for | Real-time, streaming | Batch, accuracy-critical |

For streaming with visual feedback (alpha/omega), tiny's accuracy is acceptable.

## Testing

```bash
# Verify VAD works
python -c "
from matilda_ears.transcription.streaming.vad import SileroVAD
import numpy as np

vad = SileroVAD()
silence = np.zeros(1600, dtype=np.int16)
speech = np.random.randint(-1000, 1000, 1600, dtype=np.int16)

assert not vad.is_speech(silence)
print('VAD gate working')
"

# Benchmark
python -c "
import time
from matilda_ears.transcription.streaming import StreamingAdapter, StreamingConfig

config = StreamingConfig(model_size='tiny', vad_enabled=True)
adapter = StreamingAdapter(config)
# ... timing tests
"
```

## Rollout

1. Add vad.py
2. Update adapter.py with VAD + coalescing
3. Change default model to tiny
4. Test with replay page
5. If accuracy insufficient, try "base" (74M params, ~3x faster than small)
