# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GOOBITS STT is a pure speech-to-text engine with multiple operation modes including:
- **Listen-once mode**: Single utterance capture with VAD
- **Conversation mode**: Always listening with interruption support  
- **Tap-to-talk mode**: Press key to start/stop recording
- **Hold-to-talk mode**: Hold key to record, release to stop
- **WebSocket server mode**: Remote client connections

The project is built around Whisper models for transcription and includes advanced text formatting capabilities.

## Development Commands

### Testing (Primary workflow)
```bash
./test.py                                    # Show comprehensive help
./test.py tests/text_formatting/ --summary  # Main testing workflow (YAML summary)
./test.py tests/text_formatting/ --sequential  # Sequential mode for debugging
./test.py --diff=-1                          # Check changes vs last run
./test.py --history                          # View test run history
./test.py --install                          # Install dependencies with verification
```

### Advanced Testing Options
```bash
# Execution modes
./test.py --parallel 4                       # Use 4 parallel workers
./test.py --parallel off                     # Force sequential execution

# Analysis and tracking
./test.py --detailed                         # Show detailed failure analysis
./test.py --full-diff                        # Show full assertion diffs
./test.py --track-diff                       # Auto-track changes vs last run

# Direct pytest (if preferred)
pytest tests/text_formatting/ --track-diff --sequential
pytest tests/text_formatting/ -n 4 --detailed
pytest tests/text_formatting/ --summary
```

### Code Quality
```bash
# Format code with black
black src/ tests/ stt.py

# Lint with ruff
ruff check src/ tests/ stt.py

# Fix auto-fixable issues
ruff check --fix src/ tests/ stt.py

# Type checking with mypy
mypy src/ stt.py

# Security scanning
bandit -r src/
```

### Running the Application
```bash
# Install in development mode
pip install -e .[dev]

# Run different STT modes
python stt.py --listen-once
python stt.py --conversation  
python stt.py --tap-to-talk=f8
python stt.py --hold-to-talk=space
python stt.py --server --port=8769

# Note: For development, use python stt.py directly as shown above
```

## Architecture

### Core Components
- **`src/core/config.py`**: Centralized configuration management with JSON/JSONC support
- **`src/transcription/`**: WebSocket server and client implementations for STT services
- **`src/text_formatting/`**: Advanced text formatting with entity detection and i18n support
- **`src/audio/`**: Audio capture, streaming, and Opus encoding/decoding
- **`src/modes/`**: Different operation modes (listen_once, conversation, tap-to-talk, hold-to-talk)

### Architectural Patterns
- **Async/Await Design**: All operation modes use asyncio with non-blocking `run()` methods
- **Modular Components**: Each major feature is isolated with conditional imports to prevent hard dependencies
- **Configuration-Driven**: Single `config.json` controls all behavior with auto-detection capabilities
- **Plugin-like Modes**: Operation modes are self-contained classes that can be easily extended

### Configuration System
The project uses a centralized configuration system:
- **Main config**: `config.json` in project root
- **Config loader**: `src/core/config.py` with auto-detection of CUDA, JWT secret generation
- **Platform-specific paths**: Supports Linux, macOS, Windows with automatic detection

### Text Formatting Engine
Advanced text formatting system in `src/text_formatting/`:
- **Entity detection**: Numbers, dates, code blocks, web URLs, financial amounts
- **Internationalization**: Support for multiple languages (English, Spanish)
- **Pattern conversion**: Regex-based text transformation
- **Contextual formatting**: Smart formatting based on content context

### Docker Support
Complete Docker deployment in `docker/` directory:
- Production-ready server with admin dashboard
- End-to-end encryption with RSA + AES
- JWT authentication with QR code generation
- GPU acceleration support (CUDA 12.1)

## Key Technical Details

### Dependencies
- **Core STT**: faster-whisper, ctranslate2, torch
- **Audio**: opuslib for streaming, pynput for hotkeys
- **Networking**: websockets, aiohttp for server functionality
- **Text Processing**: spacy, deepmultilingualpunctuation for formatting
- **Security**: cryptography, PyJWT for encryption and auth

### Logging
Centralized logging system via `src/core/config.py`:
```python
from src.core.config import setup_logging
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

1. **Setup**: Install with `pip install -e .[dev]` for development dependencies
2. **Configuration**: Modify `config.json` for local settings
3. **Testing**: Run `pytest` before committing changes
4. **Code Quality**: Use `ruff` and `black` for formatting, `mypy` for type checking
5. **Audio Testing**: Use test fixtures in `tests/__fixtures__/audio/`

## Important File Paths

- **Entry point**: `stt.py` - Main CLI interface
- **Server**: `src/transcription/server.py` - WebSocket server implementation
- **Config**: `config.json` - Main configuration file
- **Tests**: `tests/` - Comprehensive test suite
- **Docker**: `docker/` - Production deployment files
- **Logs**: `logs/` - Runtime log files (auto-created)

### Temporary Files
When creating temporary debug or test scripts, use `/tmp` directory to keep the project clean.