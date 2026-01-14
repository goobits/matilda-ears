# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project Overview

**Package**: `goobits-matilda-ears` | **Command**: `ears` | **Python**: 3.11+

Matilda Ears is a speech-to-text engine with multiple operation modes and an Ears Tuner pipeline.

## Core Commands

### Testing
```bash
./scripts/test.py tests/ears_tuner/ --summary
./scripts/test.py --diff=-1
./scripts/test.py --install
```

### Quality
```bash
black src/ tests/
ruff check src/ tests/
mypy src/matilda_ears/
```

### Run Modes
```bash
ears --listen-once
ears --conversation
ears --tap-to-talk=f8
ears --hold-to-talk=space
ears --server --port=3211
```

## Architecture Map

- `src/matilda_ears/core/config.py`: configuration and logging
- `src/matilda_ears/transcription/`: backends + WebSocket server
- `../matilda-ears-tuner/src/matilda_ears_tuner/`: entity detection + formatting
- `src/matilda_ears/audio/`: capture + streaming
- `src/matilda_ears/modes/`: run modes
- `src/matilda_ears/wake_word/`: wake word detection + training

## Key Paths

- `src/matilda_ears/cli.py`: generated CLI (do not edit)
- `src/matilda_ears/app_hooks.py`: CLI hooks (edit here)
- `goobits.yaml`: CLI spec for goobits
- `~/.matilda/config.toml`: shared config (`[ears]` section)
- `tests/`: test suite
