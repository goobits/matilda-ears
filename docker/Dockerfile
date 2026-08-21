FROM python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV MATILDA_DATA_DIR=/app/data
ENV WEBSOCKET_BIND_HOST=0.0.0.0
ENV WEBSOCKET_PORT=8773
ENV WEB_BIND_HOST=0.0.0.0
ENV WEB_PORT=8080
ENV HOME=/home/matilda

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ffmpeg libgomp1 libopus0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/matilda-ears
COPY matilda-ears/docker/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes --requirement /tmp/requirements.txt

COPY matilda-transport /app/matilda-transport
COPY matilda-ears /app/matilda-ears

RUN python -m pip install --no-cache-dir --no-build-isolation --no-deps --editable /app/matilda-transport \
    && python -m pip install --no-cache-dir --no-build-isolation --no-deps --editable . \
    && useradd --create-home --uid 10001 matilda \
    && mkdir -p /app/data /app/logs /home/matilda/.cache/huggingface \
    && chown -R matilda:matilda /app/data /app/logs /home/matilda

USER matilda

EXPOSE 8080 8773 8774

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD health_port=$((WEBSOCKET_PORT + 1)); \
    curl -fsS "http://127.0.0.1:$health_port/health" || exit 1

CMD ["python", "-m", "docker.start_both"]
