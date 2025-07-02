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

# Copy requirements first for better caching
COPY install/requirements-server.txt /app/install/
# Install additional requirements for dashboard
RUN pip install --no-cache-dir -r install/requirements-server.txt \
    && pip install --no-cache-dir \
        fastapi[all] \
        uvicorn \
        websockets \
        cryptography \
        pyjwt \
        httpx

# Copy the entire project
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/logs /app/ssl /app/data /app/data/encryption

# Generate SSL certificates if needed
RUN python install/utils/generate_ssl_certs.py || true

# Expose both WebSocket and dashboard ports
EXPOSE 8769 8080

# Set environment variables
ENV PYTHONPATH=/app
ENV STT_DOCKER_MODE=1
ENV WEBSOCKET_PORT=8769
ENV WEB_PORT=8080
ENV WEBSOCKET_BIND_HOST=0.0.0.0

# Health check for the services
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/api/status || exit 1

# Run the server with dashboard enabled
CMD ["python", "server.py", "start", "--dashboard", "--verbose"]