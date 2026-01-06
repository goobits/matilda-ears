# Wake Word Models

This directory contains ONNX models for wake word detection.

## Quick Start (No Training Required)

Matilda uses OpenWakeWord's pre-trained models by default. Just configure your wake phrase:

```bash
# Use "Hey Jarvis" (recommended default - works immediately)
ears --wake-word --agent-aliases="Matilda:hey_jarvis"

# Or use multiple phrases
ears --wake-word --agent-aliases="Matilda:hey_jarvis,hey_mycroft"
```

## Pre-trained Models Available

These work **immediately** without any training:

| Model | Wake Phrase | Notes |
|-------|-------------|-------|
| `hey_jarvis` | "Hey Jarvis" | Recommended default |
| `hey_mycroft` | "Hey Mycroft" | Good alternative |
| `alexa` | "Alexa" | Single word |
| `hey_rhasspy` | "Hey Rhasspy" | Less common |

## Training Custom "Hey Matilda"

You can train your own model and place the resulting `.onnx` file in this directory.

### Option A: One-Cell Script (Colab)
- Copy `scripts/train-wake-word.py` into a Colab cell
- Set `TARGET_PHRASE = "hey matilda"`

### Option B: Official Notebook (Colab)
- https://colab.research.google.com/github/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb

### Option C: Modal CLI (Cloud GPU)
```bash
ears train-wake-word "hey matilda"
```

Full CLI usage: `docs/api-reference.md`.

### After Training

1. Place `hey_matilda.onnx` in this directory
2. Use it:
   ```bash
   ears --wake-word --agent-aliases="Matilda:hey_matilda"
   ```

## Training Multiple Models

You can train additional wake words for different agents:

| File | Wake Phrase | Agent |
|------|-------------|-------|
| `hey_matilda.onnx` | "Hey Matilda" | Matilda |
| `computer.onnx` | "Computer" | Matilda (Star Trek style) |
| `hey_bob.onnx` | "Hey Bob" | Bob |

## Model Specifications

- **Format**: ONNX (Open Neural Network Exchange)
- **Input**: 80ms audio frames (1280 samples @ 16kHz, 16-bit PCM)
- **Output**: Confidence score (0.0 to 1.0)
- **Size**: ~1-2MB per model
- **Latency**: ~80ms detection delay
- **CPU Usage**: ~1-2% per model during continuous listening

## Naming Convention

Models should match the wake phrase with underscores:
- "Hey Matilda" → `hey_matilda.onnx`
- "Computer" → `computer.onnx`
- "Hey Bob" → `hey_bob.onnx`

## Troubleshooting

**Model not found**: Ensure the filename matches exactly (lowercase, underscores)

**False positives**: Lower the threshold:
```bash
ears --wake-word --ww-threshold=0.7  # Higher = stricter
```

**Missed detections**: Raise the threshold:
```bash
ears --wake-word --ww-threshold=0.3  # Lower = more sensitive
```

## Community Models

Check the Home Assistant community for additional pre-trained models:
https://github.com/fwartner/home-assistant-wakewords-collection
