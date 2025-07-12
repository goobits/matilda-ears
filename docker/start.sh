#!/bin/bash
# Start both the dashboard and WebSocket server

echo "Starting Matilda Docker services..."

# Create log directory if it doesn't exist
mkdir -p /app/logs

# Start the WebSocket server in background
echo "Starting WebSocket server on port 8769..."
python /app/docker/src/simple_websocket_server.py > /app/logs/websocket.log 2>&1 &
WEBSOCKET_PID=$!

# Give WebSocket server time to start
sleep 3

# Check if WebSocket server started by checking if process exists
if kill -0 $WEBSOCKET_PID 2>/dev/null; then
    echo "WebSocket server started successfully (PID: $WEBSOCKET_PID)"
    echo "WebSocket log:"
    tail -5 /app/logs/websocket.log
else
    echo "ERROR: WebSocket server failed to start!"
    cat /app/logs/websocket.log
    exit 1
fi

# Start the dashboard server in foreground
echo "Starting dashboard server on port 8080..."
python -m uvicorn docker.src.api:app --host 0.0.0.0 --port 8080 --log-level info

# If dashboard exits, kill WebSocket server
kill $WEBSOCKET_PID