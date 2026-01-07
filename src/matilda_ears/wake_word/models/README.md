# Wake Word Models

ONNX models for wake word detection.

## Quick Start

```bash
ears --wake-word --agent-aliases="Matilda:hey_jarvis"
```

## Pretrained Models

- `hey_jarvis`
- `hey_mycroft`
- `alexa`
- `hey_rhasspy`

## Training

```bash
ears train-wake-word "hey matilda"
```

Place the resulting `.onnx` file in this directory and reference it in `--agent-aliases`.

## Naming

Use lowercase with underscores:
`hey matilda` -> `hey_matilda.onnx`

## Troubleshooting

Adjust threshold:
```bash
ears --wake-word --ww-threshold=0.7
```
