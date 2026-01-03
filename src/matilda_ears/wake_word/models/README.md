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

## Training Custom "Hey Matilda" (Google Colab)

To train a real "Hey Matilda" model (~30-60 minutes, free):

### Step 1: Open the Training Notebook

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb)

### Step 2: Configure the Training

In the notebook, set:
```python
target_phrase = "hey matilda"
model_name = "hey_matilda"
```

### Step 3: Run All Cells

The notebook will:
1. Generate ~5000 synthetic voice samples using TTS
2. Add background noise and room acoustics
3. Train the neural network
4. Export to ONNX format

### Step 4: Download and Install

1. Download `hey_matilda.onnx` from Colab
2. Place it in this directory:
   ```
   matilda-ears/src/matilda_ears/wake_word/models/hey_matilda.onnx
   ```
3. Use it:
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
