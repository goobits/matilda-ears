# STT API Reference

## CLI API (Command Line Interface)

### Operation Modes

#### 1. Listen-Once Mode
Single utterance capture with Voice Activity Detection (VAD)
```bash
stt --listen-once
stt --listen-once --json  # JSON output
```

#### 2. Conversation Mode
Always listening with interruption support
```bash
stt --conversation
```

#### 3. Tap-to-Talk Mode
Press key once to start, press again to stop
```bash
stt --tap-to-talk=f8     # Use F8 key
stt --tap-to-talk=space  # Use spacebar
```

#### 4. Hold-to-Talk Mode
Hold key to record, release to stop
```bash
stt --hold-to-talk=space  # Hold spacebar
stt --hold-to-talk=ctrl   # Hold Ctrl key
```

#### 5. File Transcription
Transcribe audio files (WAV, MP3, etc.)
```bash
stt --file recording.wav
stt --file audio.mp3 --json
```

#### 6. WebSocket Server Mode
Run as server for remote client connections
```bash
stt --server --port=8769 --host=0.0.0.0
```

### Configuration Options

```bash
# Audio Settings
--device="USB Microphone"    # Specific audio input device
--sample-rate=16000          # Audio sample rate (default: 16000 Hz)

# Model Settings
--model=base                 # Whisper model: tiny, base, small, medium, large
--language=en                # Language code: en, es, fr, de, etc.

# Output Settings
--json                       # JSON format output
--no-formatting              # Disable text formatting

# Debugging
--debug                      # Enable debug logging
--status                     # Show system status
--models                     # List available models

# Advanced
--config=/path/to/config.json  # Custom config file
```

### Examples

```bash
# Quick voice note
stt --listen-once | jq -r '.text'

# Continuous conversation logging
stt --conversation >> conversation.txt

# Transcribe file with Spanish model
stt --file audio.mp3 --language=es --model=small

# Server for remote clients
stt --server --port=8769 --debug
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
