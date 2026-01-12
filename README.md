# Matilda Ears

Speech-to-text engine with multiple operation modes, real-time transcription, and text formatting.

## Quick Start

```bash
pipx install .
./setup.sh install --dev
ears status
```

## Basic Usage

```bash
ears status
ears models
ears status --json
```

## Operation Modes

- Listen-once
- Conversation
- Tap-to-talk / Hold-to-talk
- File transcription
- WebSocket server
- Wake word

Mode implementations live in `src/matilda_ears/modes/`.

## Wake Word

Wake word models live in `src/matilda_ears/wake_word/models/`.

```bash
ears --wake-word --agent-aliases="Matilda:hey_jarvis"
ears train-wake-word "hey matilda"
```

## Configuration

Configuration lives in `~/.matilda/config.toml` under the `[ears]` section.

```bash
ears status --json
ears models --json
```

## Development

```bash
./scripts/setup.sh install --dev
python -m spacy download en_core_web_sm

./scripts/test.py --summary
./scripts/test.py tests/text_formatting/ --summary
./scripts/test.py --diff=-1

ruff check src/ tests/
black src/ tests/
mypy src/
```

## Related Projects

- Matilda
- Matilda Voice
- Matilda Brain

## License

MIT License
