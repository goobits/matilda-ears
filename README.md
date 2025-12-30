# Matilda Ears

Speech-to-text engine with multiple operation modes, real-time transcription, and advanced text formatting.

## Key Features

- **Listen-Once** - Single utterance capture with voice activity detection
- **Conversation** - Always-listening mode with interruption support
- **Hotkey Control** - Tap-to-talk and hold-to-talk with customizable keys
- **WebSocket Server** - Remote client connections with JWT authentication
- **Text Formatting** - Entity detection, number conversion, and i18n support
- **Multiple Backends** - faster-whisper (CUDA) or Parakeet (Apple Silicon)

## Quick Start

```bash
# Install with pipx (recommended)
pipx install .

# Apple Silicon (M1/M2/M3)
pipx install ".[mac]"

# Development install
./setup.sh install --dev

# Verify installation
ears status
```

**Basic usage:**

```bash
ears status                         # Show system status
ears models                         # List available models
ears status --json                  # JSON output format
```

## Operation Modes

The following operation modes are available through the Python library:

- **Listen-Once** - Single utterance capture with VAD
- **Conversation** - Always-listening mode with interruption support
- **Tap-to-Talk** - Press key to start/stop recording
- **Hold-to-Talk** - Hold key to record, release to stop
- **File Transcribe** - Transcribe audio files
- **WebSocket Server** - Remote client connections

```python
# Python API examples
from matilda_ears.modes import ConversationMode

# Conversation mode (always listening)
mode = ConversationMode(args)
await mode.run()
```

See the `src/matilda_ears/modes/` directory for mode implementations and usage.

## Configuration

Configuration is loaded from `src/matilda_ears/config.json`:

```json
{
  "transcription": {
    "backend": "auto"
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

## Transcription Backends

### faster-whisper (Default)

Cross-platform with CUDA support. The `auto` backend auto-selects `parakeet` on Apple Silicon if available, otherwise `faster_whisper`.

```json
{
  "transcription": { "backend": "auto" },
  "whisper": { "model": "base", "device": "auto" }
}
```

- Cross-platform (Linux, macOS, Windows)
- GPU acceleration (CUDA)
- Models: tiny, base, small, medium, large-v3-turbo

### Parakeet (Apple Silicon)

Optimized for M1/M2/M3 chips.

```bash
pip install "goobits-matilda-ears[mac]"
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

### HuggingFace Transformers

Alternative backend using HuggingFace pipelines.

```bash
pip install "goobits-matilda-ears[huggingface]"
```

```json
{
  "transcription": { "backend": "huggingface" },
  "huggingface": { "model": "openai/whisper-tiny", "device": "cpu" }
}
```

## Model Comparison

| Model | Speed | Quality | Memory | Use Case |
|-------|-------|---------|--------|----------|
| tiny | Fastest | Basic | ~39MB | Real-time, low resources |
| base | Fast | Good | ~74MB | General use (default) |
| small | Moderate | Better | ~244MB | Accuracy balance |
| medium | Slower | Great | ~769MB | High accuracy |
| large-v3-turbo | Fast | Best | ~1.5GB | Production quality |

## Text Formatting

The text formatting pipeline provides:

- **Entity detection**: Phone numbers, URLs, emails, filenames, code blocks
- **Number conversion**: "three point one four" to "3.14"
- **Symbol replacement**: "at" to "@", "dot" to "."
- **Capitalization**: Smart casing for sentences, proper nouns
- **Language support**: English, Spanish

## Server Deployment

### Docker (Recommended)

```bash
cd docker
docker-compose up
```

This starts the server with:
- WebSocket server on port 8773
- Admin dashboard on port 8081 (internal 8080)

### Python Server

The server is designed to be started via the management script. For programmatic access:

```python
from matilda_ears.transcription.server.core import MatildaWebSocketServer
import asyncio

server = MatildaWebSocketServer()
asyncio.run(server.start_server())
```

### Authentication

```bash
# Generate token
python scripts/generate_token.py "Dev Client" --days 30 --show-full-token
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

## Development

```bash
# Install dev dependencies
./scripts/setup.sh install --dev
python -m spacy download en_core_web_sm

# Run tests
./scripts/test.py                                   # Show help and examples
./scripts/test.py tests/text_formatting/ --summary  # Text formatting tests
./scripts/test.py --diff=-1                         # Compare with last run
pytest -v -n auto                           # Parallel execution

# Code quality
ruff check src/ tests/
black src/ tests/
mypy src/
```

## Related Projects

- **Matilda** - AI assistant orchestrator
- **Matilda Voice** - Text-to-speech engine
- **Matilda Brain** - Text-to-text processing

## Tech Stack

**Core:** OpenAI Whisper (faster-whisper), CTranslate2, PyTorch
**Apple Silicon:** MLX, Parakeet
**Audio:** OpusLib, pynput, NumPy
**Text Processing:** spaCy, deepmultilingualpunctuation
**Server:** WebSockets, aiohttp, JWT authentication
**Deployment:** Docker, RSA+AES encryption

## License

MIT License
