# 🎙️ Goobits STT

A pure speech-to-text engine with multiple operation modes and advanced text formatting. Features real-time transcription, WebSocket server capabilities, and comprehensive text processing with internationalization support. Built on Whisper models for accurate transcription across various languages and use cases.

## 🔗 Related Projects

- **[Matilda](https://github.com/goobits/matilda)** - AI assistant
- **[Goobits STT](https://github.com/goobits/stt)** - Speech-to-Text engine (this project)
- **[Goobits TTS](https://github.com/goobits/tts)** - Text-to-Speech engine
- **[Goobits TTT](https://github.com/goobits/ttt)** - Text-to-Text processing

## 📋 Table of Contents

- [Installation](#-installation)
- [Basic Usage](#-basic-usage)
- [Configuration](#️-configuration)
- [Operation Modes](#-operation-modes)
- [Performance Optimization](#-performance-optimization)
- [Text Formatting Features](#-text-formatting-features)
- [Server Deployment](#-server-deployment)
- [Testing & Development](#-testing--development)
- [Model Comparison](#-model-comparison)
- [Audio Features](#️-audio-features)
- [Tech Stack](#️-tech-stack)

## 📦 Installation

```bash
# Install globally with pipx (recommended)
pipx install .                     # Install globally, isolated environment
pipx install .[dev]               # Install with development dependencies

# Or with pip for development
pip install -e .[dev]              # Install editable with dev dependencies
stt --version                      # Verify installation
stt --listen-once                  # Test basic functionality
```

## 🎯 Basic Usage

```bash
stt --listen-once                  # Single utterance with VAD
stt --conversation                 # Always listening mode
stt --tap-to-talk=f8              # Tap F8 to start/stop recording
stt --hold-to-talk=space          # Hold spacebar to record
stt --server --port=8769          # Run WebSocket server
```

## ⚙️ Configuration

```bash
# Edit main configuration
nano config.json

# Configure Whisper model
stt --model large-v3-turbo --language en

# Audio settings
stt --device "USB Audio" --sample-rate 16000

# Output formats
stt --format json | jq -r '.text'
stt --format text --no-formatting
```

## 🎤 Operation Modes

```bash
# Quick transcription
stt --listen-once | llm-process

# Interactive conversation
stt --conversation | tts-speak

# Hotkey control
stt --tap-to-talk=f8              # Toggle recording with F8
stt --hold-to-talk=ctrl+space     # Push-to-talk mode

# Server mode for remote clients
stt --server --host 0.0.0.0 --port 8769
```

## 🚀 Performance Optimization

```bash
# GPU acceleration (if available)
stt --model base --device cuda

# CPU optimization
stt --model tiny --device cpu

# Model selection by speed/quality
stt --model tiny      # Fastest, lower quality
stt --model base      # Balanced (default)
stt --model large-v3-turbo  # Best quality
```

## 🎭 Text Formatting Features

```bash
# Advanced entity detection
stt --listen-once  # "Call me at 555-123-4567" → "Call me at (555) 123-4567"
stt --listen-once  # "Go to github dot com" → "Go to github.com"
stt --listen-once  # "Three point one four" → "3.14"

# Multilingual support
stt --language es  # Spanish formatting rules
stt --language en  # English formatting (default)

# Disable formatting
stt --no-formatting  # Raw transcription output
```

## 🔧 Server Deployment

```bash
# Basic server
stt --server

# Production with SSL
stt --server --port 443 --host 0.0.0.0

# Docker deployment
docker run -p 8080:8080 -p 8769:8769 sttservice/transcribe
```

## 🎯 Testing & Development

```bash
# Run test suite
pytest                             # All tests
pytest tests/text_formatting/     # Specific module
pytest -v -n auto                 # Parallel with verbose output

# Code quality
ruff check src/ tests/             # Linting
black src/ tests/ stt.py          # Formatting
mypy src/ stt.py                  # Type checking

# Test with real audio
pytest tests/__fixtures__/audio/
```

## 🔧 Model Comparison

| Model | Speed | Quality | Memory | Best For |
|-------|-------|---------|---------|----------|
| **tiny** | ⚡ Fastest | 🌟 Basic | 💾 39MB | Real-time, low resources |
| **base** | 🔥 Fast | 🌟🌟 Good | 💾 74MB | General use (default) |
| **small** | ⚡ Quick | 🌟🌟🌟 Better | 💾 244MB | Accuracy balance |
| **medium** | 🔥 Moderate | 🌟🌟🌟🌟 Great | 💾 769MB | High accuracy |
| **large-v3-turbo** | 🔥 Fast | 🏆 Best | 💾 1550MB | Production quality |

Choose based on your speed/accuracy requirements and available system resources.

## 🎙️ Audio Features

- **Real-time streaming**: Opus audio encoding for efficient transmission
- **Voice Activity Detection**: Automatic speech detection and silence handling  
- **Multiple input devices**: Support for various microphones and audio interfaces
- **Hotkey integration**: System-wide keyboard shortcuts for hands-free operation
- **Background operation**: Run as daemon with minimal resource usage

## 🛠️ Tech Stack

### Core Technologies
- **🧠 AI/ML**: OpenAI Whisper (faster-whisper), CTranslate2, PyTorch
- **🎙️ Audio**: OpusLib, NumPy, custom pipe-based audio capture
- **⌨️ System**: pynput for global hotkeys, cross-platform support

### Text Processing
- **📝 NLP**: spaCy, deepmultilingualpunctuation
- **🌍 i18n**: Multi-language entity detection and formatting
- **🔧 Parsing**: pyparsing for complex text transformations
- **📊 Output**: JSON/text formatting with rich entity support

### Development & Testing
- **🧪 Testing**: pytest with asyncio, xdist, custom plugins
- **📊 Quality**: ruff (linting), black (formatting), mypy (typing)
- **🔍 Security**: bandit for security analysis
- **📦 Build**: setuptools, pyproject.toml configuration

### Deployment
- **🐳 Containerization**: Docker with CUDA 12.1 support
- **🖥️ Interface**: FastAPI admin dashboard (Docker), responsive web UI
- **🔒 Security**: JWT authentication, RSA+AES encryption (Docker)
- **📈 Monitoring**: Structured logging, health checks
- **☁️ Cloud**: Ready for production deployment with SSL/TLS