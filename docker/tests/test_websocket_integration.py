#!/usr/bin/env python3
"""Integration test for Docker API WebSocket transcription - requires running WebSocket server"""

import asyncio
import base64
import json
import os
import ssl
import sys
import tempfile
import wave
import numpy as np
import websockets

# Add docker src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from docker.src.api import DashboardAPI


def create_test_audio():
    """Create a test WAV file with a tone"""
    sample_rate = 16000
    duration = 2  # 2 seconds
    frequency = 440  # A4 note

    # Generate a sine wave
    t = np.linspace(0, duration, int(sample_rate * duration))
    samples = (np.sin(2 * np.pi * frequency * t) * 0.3 * 32767).astype(np.int16)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
        with wave.open(tmp_file.name, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(samples.tobytes())
        return tmp_file.name, samples.tobytes()


async def test_websocket_server_direct():
    """Test direct connection to WebSocket server"""
    print("\n1. Testing Direct WebSocket Connection")
    print("=" * 50)

    # Get connection parameters from environment
    host = os.getenv("WEBSOCKET_HOST", "localhost")
    port = int(os.getenv("WEBSOCKET_PORT", "8765"))
    ssl_enabled = os.getenv("SSL_ENABLED", "true").lower() == "true"
    auth_token = os.getenv("AUTH_TOKEN", "")

    protocol = "wss" if ssl_enabled else "ws"
    url = f"{protocol}://{host}:{port}"

    print(f"Connecting to: {url}")

    # Create test audio
    audio_file, audio_data = create_test_audio()

    try:
        # Create SSL context
        ssl_context = None
        if ssl_enabled:
            ssl_context = ssl.create_default_context()
            if os.getenv("SSL_VERIFY_MODE", "verify").lower() == "none":
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

        # Connect to WebSocket
        async with websockets.connect(url, ssl=ssl_context) as websocket:
            print("✅ Connected to WebSocket server")

            # Wait for welcome
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            print(f"✅ Received welcome: {welcome_data['type']}")

            # Send transcription request
            with open(audio_file, "rb") as f:
                audio_bytes = f.read()

            request = {
                "type": "transcribe",
                "token": auth_token,
                "audio_data": base64.b64encode(audio_bytes).decode("utf-8"),
                "filename": "test.wav",
                "audio_format": "wav",
            }

            await websocket.send(json.dumps(request))
            print("✅ Sent transcription request")

            # Get response
            response = await websocket.recv()
            response_data = json.loads(response)

            if response_data.get("type") == "transcription_complete":
                print(f"✅ Transcription: '{response_data.get('text', '')}'")
                return True
            print(f"❌ Error: {response_data}")
            return False

    except Exception as e:
        print(f"❌ Failed to connect: {type(e).__name__}: {e}")
        return False
    finally:
        os.unlink(audio_file)


async def test_docker_api_websocket():
    """Test Docker API WebSocket implementation"""
    print("\n2. Testing Docker API WebSocket Implementation")
    print("=" * 50)

    # Set up environment
    os.environ.setdefault("WEBSOCKET_HOST", "localhost")
    os.environ.setdefault("WEBSOCKET_PORT", "8765")
    os.environ.setdefault("SSL_ENABLED", "true")

    # Create API instance
    api = DashboardAPI()

    print(f"API configured for: {api.websocket_host}:{api.websocket_port}")
    print(f"SSL: {api.ssl_enabled}, Auth token: {'Yes' if api.auth_token else 'No'}")

    # Create test audio
    audio_file, _ = create_test_audio()

    try:
        with open(audio_file, "rb") as f:
            audio_data = f.read()

        # Test the transcription
        success, transcription, error = await api._transcribe_via_websocket(audio_data=audio_data, filename="test.wav")

        if success:
            print(f"✅ Success! Transcription: '{transcription}'")
            return True
        print(f"❌ Failed: {error}")
        return False

    except Exception as e:
        print(f"❌ Exception: {type(e).__name__}: {e}")
        return False
    finally:
        os.unlink(audio_file)


async def main():
    """Run all integration tests"""
    print("WebSocket Integration Tests")
    print("=" * 70)
    print("Prerequisites:")
    print("- WebSocket server must be running (./server.py start)")
    print("- Valid AUTH_TOKEN must be set")
    print(
        f"- Server should be accessible at {os.getenv('WEBSOCKET_HOST', 'localhost')}:{os.getenv('WEBSOCKET_PORT', '8765')}"
    )

    results = []

    # Test 1: Direct WebSocket connection
    try:
        result = await test_websocket_server_direct()
        results.append(("Direct WebSocket", result))
    except Exception as e:
        print(f"Test 1 failed with exception: {e}")
        results.append(("Direct WebSocket", False))

    # Test 2: Docker API implementation
    try:
        result = await test_docker_api_websocket()
        results.append(("Docker API", result))
    except Exception as e:
        print(f"Test 2 failed with exception: {e}")
        results.append(("Docker API", False))

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary:")
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {name}: {status}")

    all_passed = all(result for _, result in results)
    if all_passed:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed. Check server connection and configuration.")

    return all_passed


if __name__ == "__main__":
    # For Docker environment, default to host.docker.internal
    if os.getenv("MATILDA_DOCKER_MODE") == "1" and not os.getenv("WEBSOCKET_HOST"):
        os.environ["WEBSOCKET_HOST"] = "host.docker.internal"

    success = asyncio.run(main())
    sys.exit(0 if success else 1)
