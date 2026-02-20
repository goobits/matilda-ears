# Matilda Ears

Speech-to-text engine with multiple operation modes, real-time transcription, and Ears Tuner formatting.

## Quick Start

```bash
pipx install .
./scripts/setup.sh install --dev
ears status
```

## Basic Usage

```bash
ears status
ears models
ears status --json
./scripts/test.py --help
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

Ears Tuner settings live under `[ears.ears_tuner]`:

```toml
[ears.ears_tuner]
enabled = true
formatter = "pipeline"

[ears.ears_tuner.filename_formats]
md = "UPPER_SNAKE"
json = "lower_snake"
py = "lower_snake"
js = "camelCase"
"*" = "lower_snake"
```

```bash
ears status --json
ears models --json
```

## Development

```bash
./scripts/setup.sh install --dev
python -m spacy download en_core_web_sm

make test
make quality
```

## Documentation

- `docs/`
- `AGENTS.md`
- `CHANGELOG.md`

## Related Projects

- Matilda
- Matilda Voice
- Matilda Brain

## License

MIT License
