# Matilda Docker Server

Run the STT server and admin dashboard with Docker.

## Quick Start

```bash
docker run --gpus all -p 8080:8080 -p 8769:8769 sttservice/transcribe
docker run -p 8080:8080 -p 8769:8769 sttservice/transcribe
docker-compose up
```

Dashboard: http://localhost:8080

## Environment Variables

```bash
WHISPER_MODEL=base
GPU_ENABLED=true
MAX_CLIENTS=20
WEBSOCKET_PORT=8769
WEB_PORT=8080
WEBSOCKET_BIND_HOST=0.0.0.0
```

## Health Check

```bash
curl http://localhost:8080/api/status
```
