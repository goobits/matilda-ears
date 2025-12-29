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
./setup.sh install --dev

# Verify installation
ears --version
```

**Basic usage:**

```bash
ears status                         # Show system status
ears models                         # List available models
ears-server --port 8769             # WebSocket server
```

## 📚 Operation Modes

The following operation modes are available through the Python library:

- **Listen-Once** - Single utterance capture with VAD
- **Conversation** - Always-listening mode with interruption support
- **Tap-to-Talk** - Press key to start/stop recording
- **Hold-to-Talk** - Hold key to record, release to stop
- **WebSocket Server** - Remote client connections

```bash
# Server mode (standalone entry point)
ears-server --host 0.0.0.0 --port 8769
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

**CLI options:**

```bash
ears status --json                  # JSON output format
ears models --json                  # List models as JSON
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

The text formatting pipeline provides:

- **Entity detection**: Phone numbers, URLs, emails
- **Number conversion**: "three point one four" to "3.14"
- **Symbol replacement**: "at" to "@", "dot" to "."
- **Language support**: English, Spanish

## 🌐 Server Deployment

```bash
# Local server
ears-server

# Production
ears-server --port 443 --host 0.0.0.0

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
./setup.sh install --dev
python -m spacy download en_core_web_sm

# Run tests
./test.py                                   # All tests with help
./test.py tests/text_formatting/ --summary  # Text formatting tests
pytest -v -n auto                           # Parallel execution

# Code quality
ruff check src/ tests/
black src/ tests/
mypy src/
```

## 🔗 Related Projects

- **Matilda** - AI assistant orchestrator
- **Matilda Voice** - Text-to-speech engine
- **Matilda Brain** - Text-to-text processing

## 🛠️ Tech Stack

**Core:** OpenAI Whisper (faster-whisper), CTranslate2, PyTorch
**Apple Silicon:** MLX, Parakeet
**Audio:** OpusLib, pynput, NumPy
**Text Processing:** spaCy, deepmultilingualpunctuation
**Server:** WebSockets, FastAPI, JWT authentication
**Deployment:** Docker (CUDA 12.1), RSA+AES encryption

## 📝 License

MIT License
