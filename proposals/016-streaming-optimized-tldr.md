# Proposal 016: Streaming Optimization (TLDR)

## Problem → Solution

```
Before: chunk → block 2s → inference → block 2s → ...
After:  chunk → VAD? → buffer → [busy?] → skip : infer
```

## Tree Diff

```
matilda-ears/src/matilda_ears/transcription/streaming/
└── adapter.py
    ├── StreamingConfig
    │   ├── ~ model_size: str = "tiny"      # was "small" (6x faster)
    │   ├── + vad_enabled: bool = True
    │   └── + vad_threshold: float = 0.5
    │
    └── class StreamingAdapter
        ├── __init__()
        │   ├── + self._vad = None
        │   ├── + self._dirty = False
        │   ├── + self._inference_running = False
        │   ├── + self._pending_audio = []
        │   └── + self._last_result = StreamingResult()
        │
        ├── ~ async start()
        │   └── + if config.vad_enabled:
        │       +     from matilda_ears.audio.vad import SileroVAD
        │       +     self._vad = SileroVAD(threshold=config.vad_threshold)
        │
        ├── ~ async process_chunk(pcm)
        │   ├── - async with self._lock:
        │   │       # always runs inference, blocks
        │   │
        │   └── + # 1. VAD gate
        │       + if self._vad and self._vad.process_chunk(pcm) < threshold:
        │       +     return self._last_result
        │       +
        │       + # 2. Buffer
        │       + self._pending_audio.append(pcm)
        │       +
        │       + # 3. Coalesce
        │       + if self._inference_running:
        │       +     self._dirty = True
        │       +     return self._last_result
        │       +
        │       + return await self._run_inference_loop()
        │
        └── + async _run_inference_loop()
            + self._inference_running = True
            + while True:
            +     self._dirty = False
            +     # flush pending → model
            +     # run inference
            +     self._last_result = result
            +     if not self._dirty: break
            + self._inference_running = False
            + return self._last_result
```

## Effect

| | Before | After |
|-|--------|-------|
| Silence | Process | Skip |
| Busy | Block | Return cached |
| Model | small (244M) | tiny (39M) |
| Latency | ~2000ms | ~200-400ms |
