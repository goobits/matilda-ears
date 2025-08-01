#!/usr/bin/env python3
"""
Command verification script for STT CLI server commands.

This script verifies that the missing CLI commands are now working correctly.
"""

import subprocess
import json
import sys
import time
import os
from pathlib import Path


class CommandVerifier:
    def __init__(self):
        self.success_count = 0
        self.total_count = 0
        
    def run_command(self, cmd, description):
        """Run a command and verify it works."""
        self.total_count += 1
        print(f"\n{self.total_count}. Testing: {description}")
        print(f"   Command: {' '.join(cmd)}")
        
        # Set PYTHONPATH for running from source
        env = os.environ.copy()
        env['PYTHONPATH'] = '/workspace/stt/src'
        
        # Convert 'stt' to 'python3 -m stt.cli' for running from source
        if cmd[0] == 'stt':
            cmd = ['python3', '-m', 'stt.cli'] + cmd[1:]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=env)
            
            if result.returncode == 0:
                print(f"   ✅ SUCCESS: Exit code 0")
                if result.stdout.strip():
                    print(f"   📄 Output: {result.stdout.strip()[:200]}...")
                self.success_count += 1
                return True, result.stdout
            else:
                print(f"   ❌ FAILED: Exit code {result.returncode}")
                if result.stderr.strip():
                    print(f"   📄 Error: {result.stderr.strip()[:200]}...")
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            print(f"   ⏰ TIMEOUT: Command took too long")
            return False, "Timeout"
        except Exception as e:
            print(f"   💥 EXCEPTION: {e}")
            return False, str(e)
    
    def verify_json_output(self, output):
        """Verify that output is valid JSON."""
        try:
            data = json.loads(output)
            print(f"   📋 Valid JSON with keys: {list(data.keys())}")
            return True, data
        except json.JSONDecodeError as e:
            print(f"   ❌ Invalid JSON: {e}")
            return False, None
    
    def run_verification(self):
        """Run all verification tests."""
        print("🔧 STT CLI Command Verification")
        print("=" * 50)
        
        # Test 1: Basic CLI help
        self.run_command(['stt', '--help'], "Basic CLI help")
        
        # Test 2: Server command group help
        success, output = self.run_command(['stt', 'server', '--help'], "Server command group help")
        if success:
            if 'status' in output and 'start' in output:
                print("   ✅ Server subcommands found in help")
            else:
                print("   ⚠️  Server subcommands not found in help")
        
        # Test 3: Server status help
        self.run_command(['stt', 'server', 'status', '--help'], "Server status command help")
        
        # Test 4: Server start help  
        self.run_command(['stt', 'server', 'start', '--help'], "Server start command help")
        
        # Test 5: Server status (JSON)
        success, output = self.run_command(['stt', 'server', 'status', '--json'], "Server status with JSON output")
        if success and output.strip():
            is_json, data = self.verify_json_output(output)
            if is_json:
                healthy = data.get('healthy', False)
                status = data.get('status', 'unknown')
                print(f"   📊 Server status: {status}, healthy: {healthy}")
        
        # Test 6: Transcribe with --output parameter
        # Create a minimal test audio file for this
        test_audio_path = self.create_test_audio()
        if test_audio_path:
            success, output = self.run_command(
                ['stt', 'transcribe', str(test_audio_path), '--output', 'json'], 
                "Transcribe with --output parameter"
            )
            if success and output.strip():
                is_json, data = self.verify_json_output(output)
                if is_json:
                    print("   ✅ --output parameter working correctly")
            
            # Clean up test file
            test_audio_path.unlink()
        
        # Test 7: Check that stt command is available
        success, output = self.run_command(['stt', '--version'], "STT version check")
        
        # Summary
        print("\n" + "=" * 50)
        print(f"📊 VERIFICATION SUMMARY")
        print(f"   Passed: {self.success_count}/{self.total_count}")
        print(f"   Success Rate: {(self.success_count/self.total_count)*100:.1f}%")
        
        if self.success_count == self.total_count:
            print("   🎉 ALL TESTS PASSED!")
            return True
        else:
            print("   ⚠️  SOME TESTS FAILED")
            return False
    
    def create_test_audio(self):
        """Create a minimal test audio file."""
        try:
            import wave
            import numpy as np
            
            # Create 1 second of silence at 16kHz
            sample_rate = 16000
            duration = 1
            samples = np.zeros(sample_rate * duration, dtype=np.int16)
            
            test_path = Path("test_audio.wav")
            with wave.open(str(test_path), 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(samples.tobytes())
            
            print(f"   📁 Created test audio file: {test_path}")
            return test_path
            
        except ImportError:
            print("   ⚠️  Cannot create test audio (numpy/wave not available)")
            return None
        except Exception as e:
            print(f"   ❌ Failed to create test audio: {e}")
            return None


def main():
    """Main verification function."""
    verifier = CommandVerifier()
    success = verifier.run_verification()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()