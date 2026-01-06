# Ears API Reference

Complete CLI reference for the `ears` command.

## Commands

### Operation Modes (root options)

```bash
ears --listen-once
ears --conversation
ears --wake-word
ears --tap-to-talk=f8
ears --hold-to-talk=space
ears --file recording.wav
ears --server --port=8769 --host=0.0.0.0
```

### System Commands

```bash
ears status
ears models
ears download --model=base
ears train-wake-word "hey matilda"
```

## Options

### Operation Modes

- `--listen-once` Single utterance capture with VAD
- `--conversation` Always listening with interruption support
- `--wake-word` Always-listening wake word detection mode
- `--tap-to-talk=KEY` Tap KEY to start/stop recording
- `--hold-to-talk=KEY` Hold KEY to record, release to stop
- `--file=PATH` Transcribe audio file (WAV, MP3, etc.)
- `--server` Run as WebSocket server for remote clients
- `--port=PORT` Server port (default: 8769)
- `--host=HOST` Server host (default: 0.0.0.0)

### Wake Word

- `--agent-aliases=ALIASES` Agent wake word aliases (`Agent:phrase1,phrase2;Agent2:phrase3`)
- `--agents=AGENTS` Comma-separated agent names (legacy)
- `--ww-threshold=FLOAT` Wake word detection threshold (0.0-1.0)

### Output and Debugging

- `--json` Output JSON format
- `--debug` Enable detailed debug logging
- `--no-formatting` Disable advanced text formatting

### Model and Audio

- `--model=MODEL` Whisper model size (tiny, base, small, medium, large, large-v3-turbo)
- `--language=LANG` Language code (e.g., en, es, fr)
- `--device=DEVICE` Audio input device name or index
- `--sample-rate=HZ` Audio sample rate in Hz (default: 16000)

### Configuration

- `--config=PATH` Configuration file path

## Command Details

### `status`
Show system status and capabilities.

```bash
ears status
ears status --json
```

Options:
- `--json` Output JSON format

### `models`
List available Whisper models.

```bash
ears models
ears models --json
```

Options:
- `--json` Output JSON format

### `download`
Download a Whisper model for offline use.

```bash
ears download --model=base
ears download --model=large-v3-turbo --progress
```

Options:
- `--model=MODEL` Model size to download (tiny, base, small, medium, large-v3-turbo)
- `--progress` Show JSON progress events

### `train-wake-word`
Train a custom wake word model using Modal cloud GPU.

```bash
ears train-wake-word "hey matilda"
ears train-wake-word "hey matilda" --samples 3000 --epochs 10
```

Options:
- `--output=PATH` Output path for ONNX file (default: models/{phrase}.onnx)
- `--samples=NUM` Number of training samples to generate (default: 3000)
- `--epochs=NUM` Number of training epochs (default: 10)

By default the model is saved to `src/matilda_ears/wake_word/models/{phrase}.onnx`.

## Examples

```bash
ears --listen-once | jq -r '.text'
ears --conversation >> conversation.txt
ears --file audio.mp3 --language=es --model=small
ears --server --port=8769 --debug
```

---

## WebSocket API (Server Mode)

### Connection
```
ws://host:port (default: ws://localhost:8769)
```

### Protocol

#### 1. Connect to Server
Client connects via WebSocket

#### 2. Welcome Message (Server → Client)
```json
{
  "type": "welcome",
  "message": "Connected to Matilda WebSocket Server",
  "client_id": "abc12345",
  "server_ready": true
}
```

#### 3. Send Audio Data (Client → Server)

**Option A: Binary WAV Data**
```javascript
// Send raw WAV file bytes
websocket.send(audioBytes);  // Binary message
```

**Option B: JSON Command**
```json
{
  "type": "transcribe",
  "audio": "<base64-encoded-audio>",
  "format": "wav",
  "language": "en"
}
```

#### 4. Receive Transcription (Server → Client)

**Success Response:**
```json
{
  "text": "Hello world",
  "is_final": true
}
```

**Error Response:**
```json
{
  "text": "",
  "is_final": true,
  "error": "Error message here"
}
```

#### 5. Ping/Pong (Keep-Alive)
```json
// Client → Server
{"type": "ping"}

// Server → Client
{
  "type": "pong",
  "timestamp": 1702234567.89
}
```

### WebSocket Example (Python)

```python
import asyncio
import websockets
import json

async def transcribe_file(audio_path):
    # Read audio file
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    # Connect
    uri = "ws://localhost:8769"
    async with websockets.connect(uri) as ws:
        # Receive welcome
        welcome = await ws.recv()
        print(f"Connected: {welcome}")

        # Send audio (binary)
        await ws.send(audio_data)

        # Receive transcription
        response = await ws.recv()
        result = json.loads(response)

        if result["is_final"]:
            print(f"Transcription: {result['text']}")
            return result["text"]

asyncio.run(transcribe_file("audio.wav"))
```

### WebSocket Example (JavaScript/Node.js)

```javascript
const WebSocket = require('ws');
const fs = require('fs');

const ws = new WebSocket('ws://localhost:8769');

ws.on('open', () => {
  console.log('Connected to STT server');

  // Send audio file
  const audioData = fs.readFileSync('audio.wav');
  ws.send(audioData);
});

ws.on('message', (data) => {
  const message = JSON.parse(data.toString());

  if (message.type === 'welcome') {
    console.log('Server ready:', message.message);
  } else if (message.is_final) {
    console.log('Transcription:', message.text);
    ws.close();
  }
});
```

---

## Output Formats

### Text Format (Default)
```
Hello world
```

### JSON Format
```json
{
  "text": "Hello world",
  "is_final": true,
  "language": "en"
}
```

---

## Text Formatting Features

When `--no-formatting` is NOT used, STT applies:

1. **Entity Detection**:
   - URLs: `go to github.com` → `go to github.com`
   - Emails: `send to john at example dot com` → `send to john@example.com`
   - Code: `import numpy as np` → `import numpy as np`
   - Numbers: `one hundred twenty three` → `123`
   - Dates: `January first two thousand twenty four` → `January 1st, 2024`

2. **Symbol Replacement**:
   - `at` → `@`
   - `dot` → `.`
   - `slash` → `/`
   - `comma` → `,`

3. **Punctuation** (ML-based):
   - Auto-adds periods, commas, question marks
   - Capitalizes sentences

---

## Error Codes

### CLI Exit Codes
- `0` - Success
- `1` - General error
- `2` - Invalid arguments
- `127` - Command not found

### WebSocket Error Messages
```json
{
  "text": "",
  "is_final": true,
  "error": "Transcription failed: <reason>"
}
```

Common errors:
- "Invalid audio format"
- "Audio too short"
- "Model not loaded"
- "Rate limit exceeded"

---

## Health Check Endpoint

When server is running:
```bash
curl http://localhost:8770/health
```

Response:
```json
{
  "status": "healthy",
  "backend": "faster_whisper",
  "model": "base",
  "device": "cpu",
  "uptime": 3600
}
```
