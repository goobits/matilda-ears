#!/usr/bin/env python3
"""Verification test for STT server auto-start functionality."""

import subprocess
import time
import tempfile
import os
import sys
import json


def run_command(cmd, capture=True):
    """Run a command and return result."""
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    else:
        return subprocess.run(cmd).returncode, "", ""


def test_server_auto_start():
    """Test that transcribe with --prefer-server auto-starts the server."""
    print("🧪 Testing STT Server Auto-Start Functionality\n")
    
    # 1. Check initial server status
    print("1️⃣ Checking initial server status...")
    code, stdout, stderr = run_command(["stt", "server", "status", "--json"])
    if code == 0:
        status = json.loads(stdout)
        if status.get("healthy", False):
            print("   ⚠️  Server already running, stopping test")
            print("   Please stop the server first: pkill -f 'stt serve'")
            return False
    print("   ✅ Server is not running (as expected)")
    
    # 2. Create a test audio file
    print("\n2️⃣ Creating test audio file...")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        test_file = tmp.name
        # Create a minimal WAV header (44 bytes) + 1 second of silence
        wav_header = b'RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00'
        silence = b'\x00\x00' * 16000  # 1 second at 16kHz
        tmp.write(wav_header + silence)
    print(f"   ✅ Created test file: {test_file}")
    
    try:
        # 3. Run transcribe with --prefer-server (should auto-start server)
        print("\n3️⃣ Running transcribe with --prefer-server...")
        print("   Command: stt transcribe test.wav --prefer-server --debug")
        code, stdout, stderr = run_command([
            "stt", "transcribe", test_file, 
            "--prefer-server", 
            "--debug",
            "--output", "json"
        ])
        
        if code != 0:
            print(f"   ❌ Transcribe failed: {stderr}")
            return False
        
        # Check if auto-start message appears in debug output
        full_output = stdout + stderr
        if "Auto-starting server" in full_output:
            print("   ✅ Server auto-start triggered!")
        else:
            print("   ⚠️  No auto-start message found (server might have been already running)")
        
        # 4. Verify server is now running
        print("\n4️⃣ Verifying server is now running...")
        time.sleep(1)  # Give server time to fully start
        code, stdout, stderr = run_command(["stt", "server", "status", "--json"])
        if code == 0:
            status = json.loads(stdout)
            if status.get("healthy", False):
                print("   ✅ Server is now running!")
            else:
                print("   ❌ Server is not healthy")
                return False
        else:
            print("   ❌ Failed to check server status")
            return False
        
        # 5. Test direct server usage
        print("\n5️⃣ Testing direct server mode (should use running server)...")
        code, stdout, stderr = run_command([
            "stt", "transcribe", test_file, 
            "--server-only",
            "--output", "json"
        ])
        
        if code == 0:
            print("   ✅ Server-only mode works!")
        else:
            print(f"   ❌ Server-only mode failed: {stderr}")
            return False
        
        # 6. Parse transcription result
        try:
            result = json.loads(stdout)
            if result.get("success"):
                print(f"   ✅ Transcription successful")
                print(f"   📝 Text: '{result.get('text', '')}'")
                print(f"   ⏱️  Duration: {result.get('duration', 0):.2f}s")
            else:
                print(f"   ⚠️  Transcription returned: {result}")
        except:
            print("   ⚠️  Could not parse JSON result")
        
        print("\n✅ All tests passed! Auto-start functionality is working correctly.")
        return True
        
    finally:
        # Cleanup
        if os.path.exists(test_file):
            os.unlink(test_file)
        print("\n🧹 Cleaned up test file")


def main():
    """Run verification tests."""
    print("=" * 60)
    print("STT Server Auto-Start Verification Test")
    print("=" * 60)
    
    # Check if stt command is available
    code, stdout, stderr = run_command(["stt", "--version"])
    if code != 0:
        print("❌ Error: STT command not found. Please install goobits-stt first.")
        sys.exit(1)
    
    print(f"STT Version: {stdout.strip()}\n")
    
    # Run the test
    success = test_server_auto_start()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ VERIFICATION PASSED")
        print("The auto-start functionality is working as expected!")
    else:
        print("❌ VERIFICATION FAILED")
        print("Please check the implementation.")
    print("=" * 60)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()