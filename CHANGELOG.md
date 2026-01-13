# Changelog

All notable changes to Matilda Ears will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-01-12

### Added
- **SimulStreaming** - Real-time streaming transcription replacing whisper_streaming
- **Parakeet MLX Adapter** - Native Apple Silicon streaming support
- **Pluggable Wake Word Backends** - Modular wake word detection system
- **VAD Gating** - Voice activity detection with request coalescing

### Changed
- **Ears Tuner Extracted** - Moved to standalone matilda-ears-tuner package
- **TOML Configuration** - Standardized config format across all Matilda components
- **Internal Architecture** - Moved streaming adapters, backend wrappers, and helpers to internal package
- **XDG Cache** - Whisper models now use XDG-compliant cache directory

### Fixed
- PCM conversion utilities deduplicated
- VAD chunk handling and streaming robustness
- Non-iterable word timestamps guard
- Faster-whisper backend unit test mocks

### Removed
- Legacy JSON configuration support
- Redundant streaming proposals (014, 015, 016)

## [1.0.0] - 2025-10-01

### Added
- Initial release with multi-backend STT support
- Faster Whisper integration
- WebSocket server mode
- Multiple operation modes (listen-once, conversation, push-to-talk)
- Wake word detection with OpenWakeWord

[1.1.0]: https://github.com/goobits/matilda-ears/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/goobits/matilda-ears/releases/tag/v1.0.0
