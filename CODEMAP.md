```
================================================================================
                          📍 PROJECT CODEMAP
================================================================================

PROJECT SUMMARY
---------------
  Name:         GOOBITS STT
  Type:         Speech-to-Text CLI/Server
  Language:     Python 3.8+
  Framework:    WebSockets, Whisper, asyncio (FastAPI for Docker dashboard)
  Entry Point:  stt command (from src/stt/cli.py)
  
  Total Files:  175+ (143 source, 31 test, 4 config)
  Total LOC:    ~15000 (est. from samples)

================================================================================

🏗️ ARCHITECTURE OVERVIEW
------------------------

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  CLI Modes  │────▶│   Audio     │────▶│  Whisper    │
│  [5 types]  │     │  Capture    │     │   Models    │
└─────────────┘     └─────────────┘     └─────────────┘
        │                   │                    │
   [Async/Await]       [Streaming]          [Transcribe]
  (Mode Pattern)      (Opus/VAD)           (faster-whisper)
        │                   │                    │
        └───────────────────┼────────────────────┘
                            ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ WebSocket   │────▶│    Text     │────▶│   Output    │
│   Server    │     │ Formatting  │     │ (JSON/CLI)  │
└─────────────┘     └─────────────┘     └─────────────┘

Key Patterns:
  • Async/Await: All operation modes use non-blocking run() methods
  • Plugin Architecture: Modular modes with conditional imports
  • Configuration-Driven: Single config.json controls all behavior
  • Text Processing Pipeline: 6-stage entity detection & formatting

================================================================================

📁 DIRECTORY STRUCTURE
----------------------

[root]/
├── src/stt/ [143]              [Main application source]
│   ├── cli.py                 [CLI entry point]
│   ├── core/ [5]               [Config, logging, model management]
│   │   ├── config.py          [Central config loader w/ JSONC support]
│   │   ├── logging.py         [Centralized logging system]
│   │   ├── model_manager.py   [Whisper model loading/caching]
│   │   ├── rate_limiter.py    [Request throttling]
│   │   └── token_manager.py   [JWT token management]
│   ├── modes/ [6]              [Operation modes - async pattern]
│   │   ├── base_mode.py       [Abstract base for all modes]
│   │   ├── conversation.py    [Always listening w/ interruption]
│   │   ├── listen_once.py     [Single utterance capture]
│   │   ├── tap_to_talk.py     [Press key to start/stop]
│   │   ├── hold_to_talk.py    [Hold key to record]
│   │   └── wake_word.py       [Voice activation via Porcupine]
│   ├── audio/ [6]              [Audio capture & streaming]
│   │   ├── capture.py         [Platform-specific audio input]
│   │   ├── encoder.py         [Opus encoding for streaming]
│   │   ├── decoder.py         [Opus decoding from stream]
│   │   ├── vad.py             [Voice Activity Detection]
│   │   ├── opus_batch.py      [Batch Opus processing]
│   │   └── audio_streamer.py  [Real-time streaming support]
│   ├── text_formatting/ [114] [Advanced text processing engine]
│   │   ├── formatter.py       [Main formatting pipeline controller]
│   │   ├── detectors/ [15]    [Entity detection (numbers, dates, URLs)]
│   │   ├── converters/ [13]   [Text transformation patterns]
│   │   ├── processors/ [5]    [Specialized content processors]
│   │   ├── pattern_modules/ [17] [Regex pattern definitions]
│   │   ├── formatter_components/ [11] [Pipeline steps]
│   │   └── resources/ [6]     [i18n language files (en.json, es.json, fr.json, etc)]
│   ├── transcription/ [3]      [WebSocket server/client]
│   │   ├── server.py          [Main WebSocket STT server]
│   │   ├── client.py          [WebSocket client implementation]
│   │   └── streaming.py       [Real-time streaming support]
│   └── utils/ [1]              [SSL certificate utilities]
├── tests/ [31]                 [Comprehensive test suite]
│   ├── unit/text_formatting/  [Extensive entity processing tests]
│   ├── integration/           [End-to-end testing]
│   ├── fixtures/              [Test data (audio/text samples)]
│   └── tools/                 [Custom test utilities & plugins]
├── docker/ [16]                [Production deployment]
│   ├── Dockerfile             [GPU-enabled container]
│   ├── docker-compose.yml     [Container orchestration]
│   ├── dashboard/             [Admin web interface]
│   └── src/                   [Docker-specific server code]
├── config.json                [Main configuration file]
├── pyproject.toml            [Dependencies & build config]
└── setup.sh                  [Installation script - auto-generated]

================================================================================

🔑 KEY FILES (Start Here)
-------------------------

ENTRY POINTS:
  • [src/stt/cli.py]           - CLI interface
  • [config.json]              - All configuration settings
  • [setup.sh]                 - Installation & dependency mgmt (auto-generated)

CORE LOGIC:
  • [src/stt/modes/base_mode.py] - Abstract base for operation modes
  • [src/stt/core/config.py]    - Config loader w/ auto-detection
  • [src/stt/transcription/server.py] - WebSocket STT server
  • [src/stt/text_formatting/formatter.py] - Text processing pipeline

OPERATION MODES:
  • [src/stt/modes/conversation.py] - Always-listening mode
  • [src/stt/modes/listen_once.py]  - Single-utterance mode
  • [src/stt/modes/tap_to_talk.py]  - Hotkey activation
  • [src/stt/modes/hold_to_talk.py] - Hold-to-record

TEXT PROCESSING:
  • [src/stt/text_formatting/detectors/] - Entity recognition
  • [src/stt/text_formatting/converters/] - Pattern transformation
  • [src/stt/text_formatting/resources/] - i18n support

================================================================================

🔄 DATA FLOW
------------

1. Audio Input Path:
   [modes/] → [audio/capture.py] → [audio/vad.py] → [encoder.py]

2. Transcription Path:
   [audio stream] → [faster-whisper] → [base_mode.py] → [text_formatting/]

3. Text Processing Pipeline:
   [formatter.py] → [detectors/] → [converters/] → [processors/] → [output]

4. WebSocket Server Path:
   [transcription/server.py] → [JWT auth] → [streaming.py] → [client response]

Key Dependencies:
  • [base_mode] depends on → [config.py], [model_manager.py], [capture.py]
  • [formatter.py] depends on → [detectors/], [converters/], [processors/]
  • [server.py] depends on → [base_mode], [streaming.py], [encryption]
  • [cli.py] imports → [all modes], [rich-click], [config]

================================================================================

📦 DEPENDENCIES
---------------

CORE STT:
  • faster-whisper    - Whisper model inference
  • ctranslate2      - Optimized transformers
  • torch/torchaudio - ML framework
  • silero-vad       - Voice activity detection

AUDIO PROCESSING:
  • opuslib          - Opus codec for streaming
  • numpy            - Audio data manipulation
  • psutil           - System resource monitoring

NETWORKING:
  • websockets       - WebSocket server/client
  • aiohttp          - Async HTTP framework
  • cryptography     - End-to-end encryption
  • PyJWT            - Token authentication

TEXT PROCESSING:
  • spacy            - NLP entity recognition
  • deepmultilingualpunctuation - Punctuation restoration
  • pyparsing        - Advanced text parsing

INTERFACE:
  • rich-click       - Enhanced CLI interface
  • pynput           - Hotkey detection
  • pvporcupine      - Wake word detection

External Services:
  • Porcupine API    - Wake word engine (env: PORCUPINE_ACCESS_KEY)
  • Spacy Models     - Language models (auto-downloaded)

================================================================================

🎯 COMMON TASKS
---------------

To understand STT modes:
  Start with: [modes/base_mode.py] → [modes/listen_once.py] → [config.json]

To modify text formatting:
  Core files: [text_formatting/formatter.py], [detectors/], [converters/]
  Tests: [tests/unit/text_formatting/]

To add new operation mode:
  1. Extend BaseMode in [modes/base_mode.py]
  2. Implement async run() method
  3. Add CLI command in [cli.py]
  4. Run: ./setup.sh install --dev

To debug WebSocket server:
  1. Check logs in [logs/] directory
  2. Test with [docker/tests/test_websocket_integration.py]
  3. Verify config in [config.json] server section

================================================================================

⚡ QUICK REFERENCE
-----------------

Naming Conventions:
  • Files:       snake_case (modules), PascalCase (classes)
  • Functions:   snake_case
  • Constants:   UPPER_SNAKE_CASE
  • Async:       All mode run() methods are async

Ports/URLs:
  • WebSocket:   ws://localhost:8769 (configurable)
  • SSL:         Auto-generated certs in ssl/ directory
  • Auth:        JWT tokens (see config.json)

Commands:
  • Install:     ./setup.sh install --dev (development mode)
  • Test:        ./test.py tests/text_formatting/ --summary
  • Run STT:     stt listen
  • Server:      stt serve

Development:
  • Format:      ruff check --fix src/ tests/
  • Type Check:  mypy src/
  • Security:    bandit -r src/

================================================================================

⚠️ GOTCHAS & NOTES
------------------

• Use ./setup.sh install --dev for development (editable install recommended)
• Config supports JSONC format (// comments allowed)
• Whisper models auto-download on first use (~500MB-3GB)
• Docker deployment includes admin dashboard at /admin
• Text formatting supports 30+ entity types in English/Spanish/French
• All operation modes are async - use await in custom extensions
• Audio streaming uses Opus codec - requires opuslib dependency
• JWT secrets auto-generated if missing from config
• Platform detection auto-selects audio tools (arecord/ffmpeg)

================================================================================
```