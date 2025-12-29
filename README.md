# 🎤 Matilda Ears

Speech-to-text engine with multiple operation modes, real-time transcription, and advanced text formatting.

## ✨ Key Features

- **🎯 Listen-Once** - Single utterance capture with voice activity detection
- **🔄 Conversation** - Always-listening mode with interruption support
- **⌨️ Hotkey Control** - Tap-to-talk and hold-to-talk with customizable keys
- **🌐 WebSocket Server** - Remote client connections with JWT authentication
- **📝 Text Formatting** - Entity detection, number conversion, and i18n support
- **⚡ Multiple Backends** - faster-whisper (CUDA) or Parakeet (Apple Silicon)

## 🚀 Quick Start

```bash
# Install with pipx (recommended)
pipx install .

# Apple Silicon (M1/M2/M3)
pipx install .[mac]

# Development install
pip install -e .[dev]

# Verify installation
ears --version
```

**Basic usage:**

```bash
ears --listen-once                  # Single transcription
ears --conversation                 # Always listening
ears --tap-to-talk=f8              # Toggle with F8
ears --hold-to-talk=space          # Push-to-talk
ears --server --port=8769          # WebSocket server
```

## 📚 Operation Modes

```bash
# Pipe to other tools
ears --listen-once | llm-process
ears --conversation | tts-speak

# Hotkey modes
ears --tap-to-talk=f8              # Toggle recording
ears --hold-to-talk=ctrl+space     # Hold to record

# Server mode
ears --server --host 0.0.0.0 --port 8769
```

## ⚙️ Configuration

Edit `config.json` for persistent settings:

```json
{
  "transcription": {
    "backend": "faster_whisper"
  },
  "whisper": {
    "model": "base",
    "device": "auto",
    "compute_type": "auto"
  }
}
```

**CLI overrides:**

```bash
ears --model large-v3-turbo --language en
ears --device "USB Audio" --sample-rate 16000
ears --format json | jq -r '.text'
ears --no-formatting
```

## 🔧 Transcription Backends

### faster-whisper (Default)

Cross-platform with CUDA support.

```json
{
  "transcription": { "backend": "faster_whisper" },
  "whisper": { "model": "base", "device": "auto" }
}
```

- Cross-platform (Linux, macOS, Windows)
- GPU acceleration (CUDA)
- Models: tiny, base, small, medium, large-v3-turbo

### Parakeet (Apple Silicon)

Optimized for M1/M2/M3 chips.

```bash
pip install goobits-matilda-ears[mac]
```

```json
{
  "transcription": { "backend": "parakeet" },
  "parakeet": { "model": "mlx-community/parakeet-tdt-0.6b-v3" }
}
```

- Native Metal acceleration
- Lower memory footprint
- macOS only

## 📊 Model Comparison

| Model | Speed | Quality | Memory | Use Case |
|-------|-------|---------|--------|----------|
| tiny | Fastest | Basic | 39MB | Real-time, low resources |
| base | Fast | Good | 74MB | General use (default) |
| small | Moderate | Better | 244MB | Accuracy balance |
| medium | Slower | Great | 769MB | High accuracy |
| large-v3-turbo | Fast | Best | 1550MB | Production quality |

## 🎭 Text Formatting

```bash
# Entity detection
ears --listen-once  # "Call 555-123-4567" → "(555) 123-4567"
ears --listen-once  # "github dot com" → "github.com"
ears --listen-once  # "Three point one four" → "3.14"

# Language support
ears --language es  # Spanish
ears --language en  # English (default)

# Raw output
ears --no-formatting
```

## 🌐 Server Deployment

```bash
# Local server
ears --server

# Production
ears --server --port 443 --host 0.0.0.0

# Docker
docker run -p 8080:8080 -p 8769:8769 sttservice/transcribe
```

### Authentication

```bash
# Generate token
python scripts/generate_token.py "Dev Client" --days 30 --show-full-token

# Client authentication
export JWT_TOKEN="your.jwt.token"
```

**WebSocket auth message:**

```json
{ "type": "auth", "token": "YOUR_TOKEN_HERE" }
```

### Streaming Protocol

**Partial result:**

```json
{
  "type": "partial_result",
  "session_id": "...",
  "confirmed_text": "stable text",
  "tentative_text": "draft text",
  "is_final": false
}
```

**Final result:**

```json
{
  "type": "stream_transcription_complete",
  "session_id": "...",
  "confirmed_text": "final text",
  "success": true
}
```

## 🧪 Development

```bash
# Install dev dependencies
pip install -e .[dev]
python -m spacy download en_core_web_sm

# Run tests
pytest                            # All tests
pytest tests/text_formatting/    # Specific module
pytest -v -n auto                # Parallel execution

# Code quality
ruff check src/ tests/
black src/ tests/
mypy src/
```

## 🔗 Related Projects

- **[Matilda](https://github.com/goobits/matilda)** - AI assistant orchestrator
- **[Matilda Voice](https://github.com/goobits/matilda-voice)** - Text-to-speech engine
- **[Matilda Brain](https://github.com/goobits/matilda-brain)** - Text-to-text processing

## 🛠️ Tech Stack

**Core:** OpenAI Whisper (faster-whisper), CTranslate2, PyTorch
**Apple Silicon:** MLX, Parakeet
**Audio:** OpusLib, pynput, NumPy
**Text Processing:** spaCy, deepmultilingualpunctuation
**Server:** WebSockets, FastAPI, JWT authentication
**Deployment:** Docker (CUDA 12.1), RSA+AES encryption

## 📝 License

MIT License
