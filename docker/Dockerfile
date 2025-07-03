# Use Python slim base image 
FROM python:3.12-slim

# Install system dependencies including OpenSSL for certificates and curl for health checks
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    git \
    openssl \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch with GPU support first
RUN pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install other dependencies from PyPI
RUN pip install --no-cache-dir \
    faster-whisper \
    fastapi[all] \
    uvicorn \
    websockets \
    cryptography \
    pyjwt \
    httpx \
    pydantic \
    python-multipart \
    ffmpeg-python

# Copy the entire project from parent directory
COPY .. /app/

# Create necessary directories
RUN mkdir -p /app/logs /app/ssl /app/data /app/data/encryption

# Generate SSL certificates
RUN openssl req -x509 -newkey rsa:4096 \
    -keyout /app/ssl/key.pem \
    -out /app/ssl/cert.pem \
    -days 365 -nodes \
    -subj "/C=US/ST=State/L=City/O=STT/OU=Server/CN=localhost" || true

# Expose both WebSocket and dashboard ports
EXPOSE 8769 8080

# Set environment variables
ENV PYTHONPATH=/app
ENV STT_DOCKER_MODE=1
ENV WEBSOCKET_PORT=8769
ENV WEB_PORT=8080
ENV WEBSOCKET_BIND_HOST=0.0.0.0

# Whisper GPU settings - will auto-detect GPU when available
ENV WHISPER_DEVICE=auto
ENV WHISPER_COMPUTE_TYPE=auto

# Health check for the services
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/api/status || exit 1

# Run both servers (startup script is already copied with COPY .. /app/)
CMD ["python", "/app/docker/start_both.py"]