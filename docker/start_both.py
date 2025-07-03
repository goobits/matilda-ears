#!/usr/bin/env python3
"""Start both dashboard and WebSocket server"""
import subprocess
import sys
import time
import signal
import os


def signal_handler(sig, frame):
    print("\nShutting down services...")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

print("Starting STT Docker services...")

# Start WebSocket server
websocket_port = os.getenv("WEBSOCKET_PORT", "8773")
websocket_host = os.getenv("WEBSOCKET_BIND_HOST", "0.0.0.0")
print(f"Environment check - WEBSOCKET_PORT: {websocket_port}, WEBSOCKET_BIND_HOST: {websocket_host}")
print(f"Starting WebSocket server on {websocket_host}:{websocket_port}...")

# Don't capture output so we can see WebSocket server logs
ws_process = subprocess.Popen([sys.executable, "/app/docker/src/simple_websocket_server.py"])

# Wait a bit and check if it started
time.sleep(3)
if ws_process.poll() is None:
    print(f"WebSocket server started successfully (PID: {ws_process.pid})")
else:
    print("ERROR: WebSocket server failed to start!")
    sys.exit(1)

# Start dashboard server
print("Starting dashboard server on port 8080...")
try:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "docker.src.api:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8080",
            "--log-level",
            "info",
        ],
        check=False,
    )
except KeyboardInterrupt:
    pass
finally:
    # Kill WebSocket server when dashboard exits
    if ws_process.poll() is None:
        ws_process.terminate()
        ws_process.wait()
    print("All services stopped.")
