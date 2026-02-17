# Ears Boundaries

## Public API
- `matilda_ears.audio` exposes explicit types only (no `import *` leakage).
- `matilda_ears.transcription.streaming.adapter` is the only module allowed to import `matilda_ears.transcription.streaming.vendor`.

## Dependency Rules
- `audio` must not import `transcription` or `wake_word`.
- `transcription` may depend on `audio` primitives.
- IO-heavy entrypoints live under `matilda_ears.service`.

