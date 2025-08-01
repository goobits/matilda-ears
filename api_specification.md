# STT Transcribe Command API Specification

## Overview

The `stt transcribe` command provides file-based audio transcription with multiple output formats, designed specifically to support Matilda integration while being useful for general audio processing workflows.

## Command Syntax

```bash
stt transcribe AUDIO_FILES... [OPTIONS]
```

## Arguments

- `AUDIO_FILES`: One or more audio file paths to transcribe (required)
  - Supported formats: WAV, MP3, Opus
  - Accepts multiple files for batch processing

## Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--model` | `-m` | choice | `base` | Whisper model size (tiny, base, small, medium, large) |
| `--language` | `-l` | string | auto-detect | Language code (en, es, fr, etc.) |
| `--json` | - | flag | false | Output as JSON (legacy compatibility) |
| `--output` | `-o` | choice | `plain` | Output format (plain, json, matilda) |
| `--prefer-server` | - | flag | false | Try WebSocket server first, fallback to direct |
| `--server-only` | - | flag | false | Require WebSocket server connection |
| `--direct-only` | - | flag | false | Skip server, use direct Whisper processing |
| `--debug` | - | flag | false | Enable detailed debug logging |
| `--config` | - | string | - | Path to custom config file |

## Output Formats

### Plain Text (default)

Simple text output, one file per line for multiple files:

```
# audio1.wav
This is the transcribed text from the first file.

# audio2.wav  
This is the transcribed text from the second file.
```

### JSON Format (`--json` or `--output json`)

Standard JSON output with full metadata:

**Single file:**
```json
{
  "success": true,
  "text": "This is the transcribed text",
  "confidence": 0.95,
  "duration": 2.3,
  "model": "base",
  "file_info": {
    "name": "audio.wav",
    "path": "/path/to/audio.wav",
    "size_bytes": 73728,
    "format": "wav"
  },
  "processing_mode": "direct",
  "language": "en",
  "timestamp": 1643723400.0
}
```

**Multiple files:**
```json
[
  {
    "success": true,
    "text": "First file transcription",
    "confidence": 0.95,
    "duration": 2.3,
    "model": "base",
    "file_info": {
      "name": "audio1.wav",
      "path": "/path/to/audio1.wav",
      "size_bytes": 73728,
      "format": "wav"
    },
    "processing_mode": "direct",
    "language": "en",
    "timestamp": 1643723400.0
  },
  {
    "success": true,
    "text": "Second file transcription",
    "confidence": 0.92,
    "duration": 1.8,
    "model": "base",
    "file_info": {
      "name": "audio2.wav",
      "path": "/path/to/audio2.wav",
      "size_bytes": 65536,
      "format": "wav"
    },
    "processing_mode": "direct",
    "language": "en",
    "timestamp": 1643723402.0
  }
]
```

### Matilda Format (`--output matilda`)

Optimized format for Matilda TranscriptionClient compatibility:

**Single file:**
```json
{
  "success": true,
  "text": "This is the transcribed text",
  "confidence": 0.95,
  "duration": 2.3,
  "model": "base"
}
```

**Error case:**
```json
{
  "success": false,
  "text": "",
  "error": "Audio file not found: missing.wav"
}
```

## Processing Modes

### Direct Processing (default)
- Uses local Whisper model directly
- No network dependency
- Suitable for offline use

### Server Processing
- Uses WebSocket server if available
- 2-3x faster than direct processing
- 90% memory reduction vs subprocess calls
- Falls back to direct if server unavailable (with `--prefer-server`)

## Exit Codes

- `0`: Success (all files processed successfully)
- `1`: Error (file not found, transcription failed, or some files failed in batch)
- `130`: Interrupted by user (Ctrl+C)

## Error Handling

### File Not Found
```bash
$ stt transcribe missing.wav --json
❌ Error: Audio file not found: missing.wav
# Exit code: 1
```

### Transcription Error
```json
{
  "success": false,
  "text": "",
  "error": "Transcription failed: Model loading error",
  "file_info": {
    "name": "audio.wav",
    "path": "/path/to/audio.wav",
    "size_bytes": 73728,
    "format": "wav"
  },
  "timestamp": 1643723400.0
}
```

## Matilda Integration Examples

### Basic transcription (as called by Matilda)
```bash
stt transcribe audio.wav --json
```

### Batch processing
```bash
stt transcribe *.wav --output matilda
```

### Server-preferred mode
```bash
stt transcribe audio.wav --json --prefer-server
```

## Performance Characteristics

- **Direct mode**: Same performance as raw Whisper calls
- **Server mode**: 2-3x faster transcription, reduced memory usage
- **Batch processing**: Linear scaling with file count
- **Model loading**: One-time cost per session in direct mode

## Supported Audio Formats

- **WAV**: PCM, various sample rates
- **MP3**: All standard bitrates
- **Opus**: Web-optimized format
- **Other**: Any format supported by faster-whisper

## Dependencies

- `faster-whisper`: Core transcription engine
- `torch`: GPU acceleration (optional)
- `ctranslate2`: Optimized inference backend

## Configuration

Uses standard STT configuration file for:
- Default model selection
- WebSocket server settings  
- Audio processing parameters
- CUDA/CPU preference