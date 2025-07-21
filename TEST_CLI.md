# STT CLI Test Commands

This file contains all valid command combinations for testing the GOOBITS STT CLI.

## Basic Commands (No Additional Options)

```bash
# Help and Information
stt
stt --help
stt --version
stt status
stt models

# Basic Operation Modes
stt listen
stt live
stt serve

# Config Management
stt config --help
stt config list
stt config get model
stt config set model base
```

## Output Format Combinations

```bash
# JSON Output
stt listen --json
stt live --json
stt listen --hold-to-talk=space --json
stt live --tap-to-talk=f8 --json

# Disable Formatting
stt listen --no-formatting
stt live --no-formatting
stt listen --hold-to-talk=space --no-formatting
stt live --tap-to-talk=f8 --no-formatting

# JSON + No Formatting
stt listen --json --no-formatting
stt live --json --no-formatting
stt listen --hold-to-talk=space --json --no-formatting
stt live --tap-to-talk=f8 --json --no-formatting
```

## Debug Mode Combinations

```bash
# Debug with each mode
stt listen --debug
stt live --debug
stt listen --hold-to-talk=space --debug
stt live --tap-to-talk=f8 --debug
stt serve --debug
stt status --debug
stt models --debug

# Debug + JSON
stt listen --debug --json
stt live --debug --json
stt listen --hold-to-talk=space --debug --json
stt live --tap-to-talk=f8 --debug --json

# Debug + No Formatting
stt listen --debug --no-formatting
stt live --debug --no-formatting
stt listen --hold-to-talk=space --debug --no-formatting

# Debug + JSON + No Formatting
stt listen --debug --json --no-formatting
stt live --debug --json --no-formatting
stt listen --hold-to-talk=space --debug --json --no-formatting
```

## Audio Configuration

```bash
# Different Whisper Models
stt listen --model=tiny
stt listen --model=base
stt listen --model=small
stt listen --model=medium
stt listen --model=large

stt live --model=tiny
stt live --model=base
stt live --model=small
stt live --model=medium
stt live --model=large

# Language Codes
stt listen --language=en
stt listen --language=es
stt listen --language=fr
stt listen --language=de
stt listen --language=it

stt live --language=en
stt live --language=es
stt live --language=fr
stt live --language=de
stt live --language=it

# Audio Devices
stt listen --device="USB Microphone"
stt listen --device="Built-in Microphone"
stt listen --device=0
stt listen --device=1
stt live --device="USB Microphone"
stt live --device="Built-in Microphone"

# Sample Rates
stt listen --sample-rate=16000
stt listen --sample-rate=22050
stt listen --sample-rate=44100
stt listen --sample-rate=48000
stt live --sample-rate=16000
stt live --sample-rate=22050
stt live --sample-rate=44100
stt live --sample-rate=48000

# Configuration-based settings (alternative to command-line options)
stt config set whisper.model small
stt config set audio.sample_rate 44100
stt config set whisper.language es
stt config set audio.device "USB Microphone"
```

## Model + Language Combinations

```bash
# English with different models
stt listen --model=tiny --language=en
stt listen --model=base --language=en
stt listen --model=small --language=en
stt listen --model=medium --language=en
stt listen --model=large --language=en

# Spanish with different models
stt live --model=tiny --language=es
stt live --model=base --language=es
stt live --model=small --language=es
stt live --model=medium --language=es
stt live --model=large --language=es

# French with hold-to-talk
stt listen --hold-to-talk=space --model=tiny --language=fr
stt listen --hold-to-talk=space --model=base --language=fr
stt listen --hold-to-talk=space --model=small --language=fr
stt listen --hold-to-talk=space --model=medium --language=fr
stt listen --hold-to-talk=space --model=large --language=fr
```

## Server Mode Combinations

```bash
# Basic Server
stt serve
stt serve --debug

# Custom Ports
stt serve --port=8769
stt serve --port=9000
stt serve --port=8080
stt serve --port=3000

# Custom Hosts
stt serve --host=localhost
stt serve --host=127.0.0.1
stt serve --host=0.0.0.0

# Server with Port + Host
stt serve --port=8769 --host=localhost
stt serve --port=9000 --host=127.0.0.1
stt serve --port=8080 --host=0.0.0.0

# Server with Debug
stt serve --port=8769 --debug
stt serve --host=localhost --debug
stt serve --port=9000 --host=127.0.0.1 --debug

# Configuration-based server settings
stt config set server.websocket.port 9000
stt config set server.websocket.host localhost
stt serve  # Uses config settings
```

## Complex Audio Combinations

```bash
# Model + Language + Device
stt listen --model=small --language=es --device="USB Microphone"
stt live --model=base --language=en --device="Built-in Microphone"
stt listen --hold-to-talk=space --model=medium --language=fr --device=0

# Model + Language + Sample Rate
stt listen --model=small --language=es --sample-rate=44100
stt live --model=base --language=en --sample-rate=48000
stt listen --hold-to-talk=space --model=medium --language=fr --sample-rate=22050

# Model + Language + Device + Sample Rate
stt listen --model=small --language=es --device="USB Microphone" --sample-rate=44100
stt live --model=base --language=en --device="Built-in Microphone" --sample-rate=48000
stt listen --hold-to-talk=space --model=medium --language=fr --device=0 --sample-rate=22050

# Using tap-to-talk with complex options
stt live --tap-to-talk=f8 --model=small --language=es --device="USB Microphone" --sample-rate=44100
stt live --tap-to-talk=space --model=base --language=en --device="Built-in Microphone" --sample-rate=48000
```

## Maximum Complexity Combinations

```bash
# Everything with listen
stt listen --model=small --language=es --device="USB Microphone" --sample-rate=44100 --json --debug --no-formatting

# Everything with live
stt live --model=base --language=en --device="Built-in Microphone" --sample-rate=48000 --json --debug --no-formatting

# Everything with hold-to-talk
stt listen --hold-to-talk=space --model=medium --language=fr --device=0 --sample-rate=22050 --json --debug --no-formatting

# Everything with tap-to-talk
stt live --tap-to-talk=f8 --model=large --language=de --device="USB Microphone" --sample-rate=44100 --json --debug --no-formatting

# Everything with server
stt serve --port=9000 --host=localhost --debug

# Using configuration + command options (config overridden by command line)
stt config set whisper.model base
stt config set whisper.language en
stt listen --model=small --language=es  # Overrides config settings
```

## Key Combinations for Tap/Hold-to-Talk

```bash
# Common Keys with live mode (tap-to-talk)
stt live --tap-to-talk=space
stt live --tap-to-talk=enter
stt live --tap-to-talk=ctrl
stt live --tap-to-talk=alt
stt live --tap-to-talk=shift
stt live --tap-to-talk=tab
stt live --tap-to-talk=esc

# Common Keys with listen mode (hold-to-talk)
stt listen --hold-to-talk=space
stt listen --hold-to-talk=enter
stt listen --hold-to-talk=ctrl
stt listen --hold-to-talk=alt
stt listen --hold-to-talk=shift
stt listen --hold-to-talk=tab
stt listen --hold-to-talk=esc

# Function Keys
stt live --tap-to-talk=f1
stt live --tap-to-talk=f2
stt live --tap-to-talk=f8
stt live --tap-to-talk=f12

stt listen --hold-to-talk=f1
stt listen --hold-to-talk=f2
stt listen --hold-to-talk=f8
stt listen --hold-to-talk=f12
```

## Configuration Management Tests

```bash
# Config management commands
stt config list
stt config get whisper.model
stt config get server.websocket.port
stt config get audio.sample_rate
stt config set whisper.model small
stt config set server.websocket.port 9000
stt config set whisper.language es
stt config set audio.device "USB Microphone"

# Custom config file paths with commands
stt listen --config=/path/to/config.json
stt live --config=./custom-config.json
stt serve --config=/etc/stt/config.json
stt listen --hold-to-talk=space --config=~/.stt/config.json

# Config with other options
stt listen --config=/path/to/config.json --debug
stt live --config=./custom-config.json --json
stt serve --config=/etc/stt/config.json --port=9000 --debug

# Testing config precedence (command line overrides config file)
stt config set whisper.model base
stt listen --model=small  # Should use 'small', not 'base'
stt config get whisper.model  # Should still show 'base'
```

## Pipeline Examples (JSON Output)

```bash
# Basic pipelines
stt listen --json | jq .
stt live --json | jq -r '.text'
stt listen --hold-to-talk=space --json | head -10

# Complex pipelines
stt listen --model=small --language=es --json | jq -r '.text' | wc -w
stt live --model=base --json --debug | tee conversation.log
stt serve --port=8769 --debug > server.log 2>&1

# Configuration pipelines
stt config list | jq '.whisper.model'
stt config get whisper.model | xargs -I {} stt listen --model={}
```

## Error Testing (Should Show Help)

```bash
# These should all show help/error messages
stt --invalid-option
stt listen live                   # Multiple subcommands not allowed
stt serve listen                  # Multiple subcommands not allowed
stt --port=8769                   # Port without serve command
stt --host=localhost              # Host without serve command
stt listen --tap-to-talk=f8       # Tap-to-talk with listen (should be live)
stt live --hold-to-talk=space     # Hold-to-talk with live (should be listen)

# Config errors
stt config                        # Missing subcommand
stt config set                    # Missing arguments
stt config set key               # Missing value
stt config get                   # Missing key
stt config get nonexistent.key   # Should show error or null
```

---

**Total Valid Combinations: ~150+**

## New Configuration-First Workflow

```bash
# Set up defaults once
stt config set whisper.model small
stt config set whisper.language es  
stt config set audio.device "USB Microphone"
stt config set server.websocket.port 9000

# Then use simple commands (will use config defaults)
stt listen
stt live
stt serve

# Override config when needed
stt listen --model=large --language=en
stt serve --port=8080
```

Note: Some combinations may require actual hardware (microphones, audio devices) to test fully. Server mode combinations may require network connectivity testing.

## Key Changes from Old CLI

- **Before**: `stt --listen-once` → **After**: `stt listen`
- **Before**: `stt --conversation` → **After**: `stt live`  
- **Before**: `stt --server` → **After**: `stt serve`
- **Before**: `stt --status` → **After**: `stt status`
- **Before**: `stt --models` → **After**: `stt models`
- **NEW**: `stt config set/get/list` for persistent settings
- **NEW**: Configuration-driven workflow with command-line overrides