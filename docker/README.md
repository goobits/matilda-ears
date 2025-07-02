# STT Docker Server

Production-ready Speech-to-Text server with admin dashboard and end-to-end encryption.

## 🚀 Quick Start

### Basic Usage
```bash
# Start the server (CPU mode)
docker run -p 8080:8080 -p 8769:8769 sttservice/transcribe

# Start with GPU acceleration
docker run --gpus all -p 8080:8080 -p 8769:8769 sttservice/transcribe

# Using docker-compose
docker-compose up
```

**Access the admin dashboard at: http://localhost:8080**

### Build from Source
```bash
# Build the Docker image
docker build -t sttservice/transcribe .

# Run with custom settings
docker run -p 8080:8080 -p 8769:8769 \
  -e WHISPER_MODEL=base \
  -e MAX_CLIENTS=50 \
  sttservice/transcribe
```

## 🎯 Features

- **Admin Dashboard**: Web interface for QR code generation and server management
- **End-to-End Encryption**: RSA + AES hybrid encryption - server operators cannot read transcriptions
- **JWT Authentication**: Secure token-based access control with configurable expiration
- **One-Time QR Codes**: Enhanced security - QR codes invalidated after first use
- **GPU Acceleration**: Automatic GPU detection and faster_whisper integration
- **Health Monitoring**: Built-in health checks and automatic restart capabilities

## 🔧 Configuration

### Environment Variables
```bash
WHISPER_MODEL=large-v3-turbo    # tiny, base, small, medium, large, large-v3-turbo
GPU_ENABLED=true                # Enable GPU acceleration
MAX_CLIENTS=20                  # Maximum concurrent clients
WEBSOCKET_PORT=8769            # WebSocket server port
WEB_PORT=8080                  # Dashboard port
WEBSOCKET_BIND_HOST=0.0.0.0    # Bind address
```

### Volumes
```bash
# Persistent data and configuration
-v /host/data:/app/data

# Custom SSL certificates
-v /host/ssl:/app/ssl

# Log persistence
-v /host/logs:/app/logs
```

## 🏗️ Architecture

```
docker/
├── src/                     # Python source code
│   ├── api.py              # FastAPI dashboard backend
│   ├── encryption.py       # End-to-end encryption module
│   ├── token_manager.py    # JWT token management
│   ├── websocket_server.py # Enhanced WebSocket server
│   ├── server_launcher.py  # Unified server management
│   └── validate_setup.py   # Testing and validation
├── dashboard/              # Web interface
│   ├── index.html         # Admin dashboard
│   ├── dashboard.js       # Frontend JavaScript
│   ├── admin.css         # Responsive styling
│   └── vendor/           # Third-party libraries
├── Dockerfile            # Container definition
├── docker-compose.yml    # Service orchestration
└── README.md            # This file
```

## 🔐 Security

- **End-to-End Encryption**: Client-side encryption ensures server operators cannot read transcriptions
- **JWT Tokens**: Secure authentication with configurable expiration
- **One-Time QR Codes**: Enhanced security for token distribution
- **Rate Limiting**: Protection against abuse (10 requests/minute per IP)
- **SSL/TLS**: Encrypted connections throughout
- **No Plaintext Storage**: All transcriptions are encrypted before reaching the server

## 📱 Client Setup

1. **Access Dashboard**: Open http://localhost:8080
2. **Generate QR Code**: Enter client name and expiration
3. **Share QR Code**: Client scans with STT Connect app
4. **Instant Connection**: Automatic encrypted connection established

## 🧪 Testing

```bash
# Validate setup without Docker
python3 src/validate_setup.py

# Test with local Python environment
python3 -m docker.src.validate_setup
```

## 🐛 Troubleshooting

### Common Issues

**Port conflicts:**
```bash
docker run -p 8081:8080 -p 8770:8769 sttservice/transcribe
```

**GPU not detected:**
```bash
# Check GPU support
docker run --gpus all nvidia/cuda:11.8-base nvidia-smi

# Force CPU mode
docker run -e GPU_ENABLED=false sttservice/transcribe
```

**Dashboard not accessible:**
- Check firewall settings for port 8080
- Use actual IP address instead of localhost
- Verify container health: `docker ps`

### Logs and Debugging
```bash
# View container logs
docker logs <container-name>

# Check service health
curl http://localhost:8080/api/status

# Monitor real-time logs
docker logs -f <container-name>
```

## 🚀 Production Deployment

### With SSL/TLS
```bash
docker run -p 443:8080 -p 8769:8769 \
  -v /etc/ssl/certs:/app/ssl \
  -e DOMAIN_NAME=transcribe.yourdomain.com \
  sttservice/transcribe
```

### With Resource Limits
```bash
docker run --memory=8g --cpus=4 \
  -p 8080:8080 -p 8769:8769 \
  sttservice/transcribe
```

### High Availability
```bash
# Scale with docker-compose
docker-compose up --scale stt-server=3
```

## 📞 Support

- **Issues**: Report problems and bugs
- **Features**: Request new functionality
- **Security**: Report security concerns privately

---

**Ready to deploy!** Start with `docker run -p 8080:8080 -p 8769:8769 sttservice/transcribe`