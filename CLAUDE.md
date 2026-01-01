# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Package**: `goobits-matilda-ears` | **Command**: `ears` | **Python**: 3.11+

Matilda Ears is a pure speech-to-text engine with multiple operation modes including:
- **Listen-once mode**: Single utterance capture with VAD
- **Conversation mode**: Always listening with interruption support  
- **Tap-to-talk mode**: Press key to start/stop recording
- **Hold-to-talk mode**: Hold key to record, release to stop
- **WebSocket server mode**: Remote client connections

The project is built around Whisper models for transcription and includes advanced text formatting capabilities.

## Development Commands

### Testing (Primary workflow)
```bash
./scripts/test.py                                    # Show comprehensive help
./scripts/test.py tests/text_formatting/ --summary  # Main testing workflow (YAML summary)
./scripts/test.py tests/text_formatting/ --sequential  # Sequential mode for debugging
./scripts/test.py --diff=-1                          # Check changes vs last run
./scripts/test.py --history                          # View test run history
./scripts/test.py --install                          # Install dependencies with verification
```

### Advanced Testing Options
```bash
# Execution modes
./scripts/test.py --parallel 4                       # Use 4 parallel workers
./scripts/test.py --parallel off                     # Force sequential execution

# Analysis and tracking
./scripts/test.py --detailed                         # Show detailed failure analysis
./scripts/test.py --full-diff                        # Show full assertion diffs
./scripts/test.py --track-diff                       # Auto-track changes vs last run

# Direct pytest (if preferred)
pytest tests/text_formatting/ --track-diff --sequential
pytest tests/text_formatting/ -n 4 --detailed
pytest tests/text_formatting/ --summary
```

### Code Quality
```bash
# Format code with black
black src/ tests/

# Lint with ruff
ruff check src/ tests/

# Fix auto-fixable issues
ruff check --fix src/ tests/

# Type checking with mypy
mypy src/matilda_ears/

# Security scanning
bandit -r src/
```

### Running the Application
```bash
# Install in development mode
./scripts/setup.sh install --dev

# Run different modes
ears --listen-once
ears --conversation
ears --tap-to-talk=f8
ears --hold-to-talk=space
ears --server --port=8769
```

## Architecture

### Core Components
- **`src/matilda_ears/core/config.py`**: Centralized configuration management with JSON/JSONC support
- **`src/matilda_ears/transcription/`**: WebSocket server and client implementations
- **`src/matilda_ears/text_formatting/`**: Advanced text formatting with entity detection and i18n support
- **`src/matilda_ears/audio/`**: Audio capture, streaming, and Opus encoding/decoding
- **`src/matilda_ears/modes/`**: Different operation modes (listen_once, conversation, tap-to-talk, hold-to-talk)

### Architectural Patterns
- **Async/Await Design**: All operation modes use asyncio with non-blocking `run()` methods
- **Modular Components**: Each major feature is isolated with conditional imports to prevent hard dependencies
- **Configuration-Driven**: Single `config.json` controls all behavior with auto-detection capabilities
- **Plugin-like Modes**: Operation modes are self-contained classes that can be easily extended

### Configuration System
The project uses a centralized configuration system:
- **Main config**: `config.json` in project root
- **Config loader**: `src/matilda_ears/core/config.py` with auto-detection of CUDA, JWT secret generation
- **Platform-specific paths**: Supports Linux, macOS, Windows with automatic detection

### Text Formatting Engine
Advanced text formatting system in `src/matilda_ears/text_formatting/`:
- **Entity detection**: Numbers, dates, code blocks, web URLs, financial amounts
- **Internationalization**: Support for multiple languages (English, Spanish)
- **Pattern conversion**: Regex-based text transformation
- **Contextual formatting**: Smart formatting based on content context

### Transcription Backends

Ears supports pluggable transcription backends for platform-specific optimization:

**Available Backends:**
- **faster_whisper** (default): CPU/CUDA Whisper implementation using CTranslate2
  - Cross-platform (Linux, macOS, Windows)
  - Supports GPU acceleration (CUDA)
  - Auto-detects optimal compute type
  - Models: tiny, base, small, medium, large-v3-turbo

- **parakeet**: Apple Silicon MLX-optimized transcription
  - macOS only (requires Metal/MLX support)
  - Optimized for M1/M2/M3 chips
  - Lower memory footprint
  - Requires `[mac]` extras: `pip install goobits-matilda-ears[mac]`

**Configuration:**

Edit `config.json`:
```json
{
  "transcription": {
    "backend": "faster_whisper"  // or "parakeet"
  },
  "whisper": {
    "model": "base",
    "device": "auto",
    "compute_type": "auto"
  },
  "parakeet": {
    "model": "mlx-community/parakeet-tdt-0.6b-v3"
  }
}
```

**Backend Selection Guide:**
- **Use faster_whisper if**: Cross-platform compatibility needed, CUDA GPU available, need larger models
- **Use parakeet if**: Running on Apple Silicon (M1/M2/M3), need lower memory usage, macOS-only deployment

**Architecture:**
- Abstract base class: `src/matilda_ears/transcription/backends/base.py`
- Implementations: `src/matilda_ears/transcription/backends/{faster_whisper,parakeet}_backend.py`
- Factory: `src/matilda_ears/transcription/backends/__init__.py:get_backend_class()`
- Server integration: `src/matilda_ears/transcription/server.py`

### Docker Support
Complete Docker deployment in `docker/` directory:
- Production-ready server with admin dashboard
- End-to-end encryption with RSA + AES
- JWT authentication with QR code generation
- GPU acceleration support (CUDA 12.1)

## Key Technical Details

### Dependencies
- **Core engine**: faster-whisper, ctranslate2, torch
- **Optional Backends**: mlx, parakeet-mlx (install with `[mac]` extras for Apple Silicon)
- **Audio**: opuslib for streaming, pynput for hotkeys
- **Networking**: websockets, aiohttp for server functionality
- **Text Processing**: spacy, deepmultilingualpunctuation for formatting
- **Security**: cryptography, PyJWT for encryption and auth

### Logging
Centralized logging system via `src/matilda_ears/core/config.py`:
```python
from matilda_ears.core.config import setup_logging
logger = setup_logging(__name__, log_level="INFO")
```
- Logs stored in `logs/` directory
- Module-specific log files
- Configurable console and file output

### Testing Framework
- **pytest** with extensive plugin support
- Custom test tools in `tests/__tools__/`
- Text formatting tests with comprehensive entity coverage
- Audio test fixtures in `tests/__fixtures__/`

## Development Workflow

1. **Setup**: Install with `./scripts/setup.sh install --dev` for development dependencies
2. **Configuration**: Modify `config.json` for local settings
3. **Testing**: Run `pytest` before committing changes
4. **Code Quality**: Use `ruff` and `black` for formatting, `mypy` for type checking
5. **Audio Testing**: Use test fixtures in `tests/__fixtures__/audio/`

## Important File Paths

- **CLI**: `src/matilda_ears/cli.py` - Generated CLI entry point (DO NOT EDIT)
- **Hooks**: `src/matilda_ears/app_hooks.py` - CLI hook implementations (EDIT THIS)
- **Config**: `goobits.yaml` - CLI configuration for goobits build
- **Server**: `src/matilda_ears/transcription/server.py` - WebSocket server implementation
- **Config**: `config.json` - Main configuration file
- **Tests**: `tests/` - Comprehensive test suite
- **Docker**: `docker/` - Production deployment files
- **Logs**: `logs/` - Runtime log files (auto-created)

### Temporary Files
When creating temporary debug or test scripts, use `/tmp` directory to keep the project clean.