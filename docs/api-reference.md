# Ears API Reference

CLI reference for the `ears` command.

## Commands

```bash
ears status
ears models
ears download --model=base
ears train-wake-word "hey matilda"
```

## Operation Modes

```bash
ears --listen-once
ears --conversation
ears --wake-word
ears --tap-to-talk=f8
ears --hold-to-talk=space
ears --file recording.wav
ears --server --port=3211 --host=0.0.0.0
```

## Common Options

- `--json`
- `--debug`
- `--no-formatting`
- `--model=MODEL`
- `--language=LANG`
- `--device=DEVICE`
- `--sample-rate=HZ`
- `--config=PATH`

## WebSocket Server

```text
ws://localhost:3211
```

Basic flow:
1. Connect.
2. Send audio bytes.
3. Receive JSON with `text` and `is_final`.

## Output

Default:
```
Hello world
```

JSON:
```json
{ "text": "Hello world", "is_final": true }
```
