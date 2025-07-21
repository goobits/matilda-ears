# STT CLI Test Commands

This file contains all valid command combinations for testing the GOOBITS STT CLI.

## Basic Commands (No Additional Options)

```bash
# Help and Information
stt
stt --help
stt --version
stt --status
stt --models

# Basic Operation Modes
stt --listen-once
stt --conversation
stt --wake-word
stt --tap-to-talk=f8
stt --tap-to-talk=space
stt --tap-to-talk=ctrl
stt --hold-to-talk=f8
stt --hold-to-talk=space
stt --hold-to-talk=ctrl
stt --server
```

## Output Format Combinations

```bash
# JSON Output
stt --listen-once --json
stt --conversation --json
stt --wake-word --json
stt --tap-to-talk=f8 --json
stt --hold-to-talk=space --json
stt --server --json

# Disable Formatting
stt --listen-once --no-formatting
stt --conversation --no-formatting
stt --wake-word --no-formatting
stt --tap-to-talk=f8 --no-formatting
stt --hold-to-talk=space --no-formatting

# JSON + No Formatting
stt --listen-once --json --no-formatting
stt --conversation --json --no-formatting
stt --wake-word --json --no-formatting
stt --tap-to-talk=f8 --json --no-formatting
stt --hold-to-talk=space --json --no-formatting
```

## Debug Mode Combinations

```bash
# Debug with each mode
stt --listen-once --debug
stt --conversation --debug
stt --wake-word --debug
stt --tap-to-talk=f8 --debug
stt --hold-to-talk=space --debug
stt --server --debug
stt --status --debug
stt --models --debug

# Debug + JSON
stt --listen-once --debug --json
stt --conversation --debug --json
stt --wake-word --debug --json
stt --tap-to-talk=f8 --debug --json
stt --hold-to-talk=space --debug --json

# Debug + No Formatting
stt --listen-once --debug --no-formatting
stt --conversation --debug --no-formatting
stt --wake-word --debug --no-formatting

# Debug + JSON + No Formatting
stt --listen-once --debug --json --no-formatting
stt --conversation --debug --json --no-formatting
stt --wake-word --debug --json --no-formatting
```

## Audio Configuration

```bash
# Different Whisper Models
stt --listen-once --model=tiny
stt --listen-once --model=base
stt --listen-once --model=small
stt --listen-once --model=medium
stt --listen-once --model=large

stt --conversation --model=tiny
stt --conversation --model=base
stt --conversation --model=small
stt --conversation --model=medium
stt --conversation --model=large

# Language Codes
stt --listen-once --language=en
stt --listen-once --language=es
stt --listen-once --language=fr
stt --listen-once --language=de
stt --listen-once --language=it

stt --conversation --language=en
stt --conversation --language=es
stt --conversation --language=fr
stt --conversation --language=de
stt --conversation --language=it

# Audio Devices
stt --listen-once --device="USB Microphone"
stt --listen-once --device="Built-in Microphone"
stt --listen-once --device=0
stt --listen-once --device=1
stt --conversation --device="USB Microphone"
stt --conversation --device="Built-in Microphone"

# Sample Rates
stt --listen-once --sample-rate=16000
stt --listen-once --sample-rate=22050
stt --listen-once --sample-rate=44100
stt --listen-once --sample-rate=48000
stt --conversation --sample-rate=16000
stt --conversation --sample-rate=22050
stt --conversation --sample-rate=44100
stt --conversation --sample-rate=48000
```

## Model + Language Combinations

```bash
# English with different models
stt --listen-once --model=tiny --language=en
stt --listen-once --model=base --language=en
stt --listen-once --model=small --language=en
stt --listen-once --model=medium --language=en
stt --listen-once --model=large --language=en

# Spanish with different models
stt --conversation --model=tiny --language=es
stt --conversation --model=base --language=es
stt --conversation --model=small --language=es
stt --conversation --model=medium --language=es
stt --conversation --model=large --language=es

# French with different models
stt --wake-word --model=tiny --language=fr
stt --wake-word --model=base --language=fr
stt --wake-word --model=small --language=fr
stt --wake-word --model=medium --language=fr
stt --wake-word --model=large --language=fr
```

## Server Mode Combinations

```bash
# Basic Server
stt --server
stt --server --debug
stt --server --json

# Custom Ports
stt --server --port=8769
stt --server --port=9000
stt --server --port=8080
stt --server --port=3000

# Custom Hosts
stt --server --host=localhost
stt --server --host=127.0.0.1
stt --server --host=0.0.0.0

# Server with Port + Host
stt --server --port=8769 --host=localhost
stt --server --port=9000 --host=127.0.0.1
stt --server --port=8080 --host=0.0.0.0

# Server with Debug
stt --server --port=8769 --debug
stt --server --host=localhost --debug
stt --server --port=9000 --host=127.0.0.1 --debug
```

## Complex Audio Combinations

```bash
# Model + Language + Device
stt --listen-once --model=small --language=es --device="USB Microphone"
stt --conversation --model=base --language=en --device="Built-in Microphone"
stt --wake-word --model=medium --language=fr --device=0

# Model + Language + Sample Rate
stt --listen-once --model=small --language=es --sample-rate=44100
stt --conversation --model=base --language=en --sample-rate=48000
stt --wake-word --model=medium --language=fr --sample-rate=22050

# Model + Language + Device + Sample Rate
stt --listen-once --model=small --language=es --device="USB Microphone" --sample-rate=44100
stt --conversation --model=base --language=en --device="Built-in Microphone" --sample-rate=48000
stt --wake-word --model=medium --language=fr --device=0 --sample-rate=22050
```

## Maximum Complexity Combinations

```bash
# Everything with listen-once
stt --listen-once --model=small --language=es --device="USB Microphone" --sample-rate=44100 --json --debug --no-formatting

# Everything with conversation
stt --conversation --model=base --language=en --device="Built-in Microphone" --sample-rate=48000 --json --debug --no-formatting

# Everything with wake-word
stt --wake-word --model=medium --language=fr --device=0 --sample-rate=22050 --json --debug --no-formatting

# Everything with tap-to-talk
stt --tap-to-talk=f8 --model=large --language=de --device="USB Microphone" --sample-rate=44100 --json --debug --no-formatting

# Everything with hold-to-talk
stt --hold-to-talk=space --model=tiny --language=it --device=1 --sample-rate=16000 --json --debug --no-formatting

# Everything with server
stt --server --port=9000 --host=localhost --json --debug
```

## Key Combinations for Tap/Hold-to-Talk

```bash
# Common Keys
stt --tap-to-talk=space
stt --tap-to-talk=enter
stt --tap-to-talk=ctrl
stt --tap-to-talk=alt
stt --tap-to-talk=shift
stt --tap-to-talk=tab
stt --tap-to-talk=esc

stt --hold-to-talk=space
stt --hold-to-talk=enter
stt --hold-to-talk=ctrl
stt --hold-to-talk=alt
stt --hold-to-talk=shift
stt --hold-to-talk=tab
stt --hold-to-talk=esc

# Function Keys
stt --tap-to-talk=f1
stt --tap-to-talk=f2
stt --tap-to-talk=f8
stt --tap-to-talk=f12

stt --hold-to-talk=f1
stt --hold-to-talk=f2
stt --hold-to-talk=f8
stt --hold-to-talk=f12
```

## Configuration File Tests

```bash
# Custom config paths
stt --listen-once --config=/path/to/config.json
stt --conversation --config=./custom-config.json
stt --server --config=/etc/stt/config.json
stt --wake-word --config=~/.stt/config.json

# Config with other options
stt --listen-once --config=/path/to/config.json --debug
stt --conversation --config=./custom-config.json --json
stt --server --config=/etc/stt/config.json --port=9000 --debug
```

## Pipeline Examples (JSON Output)

```bash
# Basic pipelines
stt --listen-once --json | jq .
stt --conversation --json | jq -r '.text'
stt --wake-word --json | head -10

# Complex pipelines
stt --listen-once --model=small --language=es --json | jq -r '.text' | wc -w
stt --conversation --model=base --json --debug | tee conversation.log
stt --server --port=8769 --json > server.log 2>&1
```

## Error Testing (Should Show Help)

```bash
# These should all show help/error messages
stt --invalid-option
stt --listen-once --conversation  # Multiple modes
stt --server --wake-word          # Multiple modes
stt --tap-to-talk                 # Missing key argument
stt --hold-to-talk                # Missing key argument
stt --port=8769                   # Port without server
stt --host=localhost              # Host without server
```

---

**Total Valid Combinations: ~200+**

Note: Some combinations may require actual hardware (microphones, audio devices) to test fully. Server mode combinations may require network connectivity testing.