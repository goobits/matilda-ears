#!/usr/bin/env python3
"""Quick test of STT WebSocket server"""
import asyncio
import json
import websockets
from pathlib import Path


async def test_stt():
    # Find test audio file relative to this script
    script_dir = Path(__file__).parent
    audio_path = script_dir / "tests" / "__fixtures__" / "audio" / "test_hello_world.wav"

    if not audio_path.exists():
        print(f"❌ Error: Test audio file not found at {audio_path}")
        print(f"   Current directory: {Path.cwd()}")
        print(f"   Script directory: {script_dir}")
        return

    # Read test audio file
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    print(f"✅ Read {len(audio_data)} bytes from {audio_path.name}")

    # Connect to STT server
    uri = "ws://localhost:8769"
    print(f"🔌 Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            # Receive welcome message
            welcome = await websocket.recv()
            print(f"👋 Welcome: {welcome}")

            # Send audio data
            print(f"📤 Sending {len(audio_data)} bytes of audio...")
            await websocket.send(audio_data)

            # Wait for transcription
            print("⏳ Waiting for transcription...")
            response = await websocket.recv()
            print(f"📥 Response: {response}")

            # Parse result
            result = json.loads(response)
            print(f"\n✅ Transcription: '{result['text']}'")
            print(f"   Is final: {result['is_final']}")
    except ConnectionRefusedError:
        print("❌ Error: Could not connect to STT server")
        print("   Make sure the server is running: stt --server --port 8769")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_stt())
