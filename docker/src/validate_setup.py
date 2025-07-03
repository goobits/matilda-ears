#!/usr/bin/env python3
"""Validation script for Docker STT Server setup
Tests imports and basic functionality without actually starting servers
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append("/workspace")


def test_imports():
    """Test that all required modules can be imported"""
    print("🔍 Testing imports...")

    try:
        # Test dashboard API imports
        from docker.src.api import DashboardAPI

        print("✅ Dashboard API imports successful")

        # Test encryption imports
        from docker.src.encryption import EncryptionManager, EncryptionWebSocketHandler

        print("✅ Encryption module imports successful")

        # Test token manager imports
        from docker.src.token_manager import TokenManager

        print("✅ Token manager imports successful")

        # Test WebSocket server imports
        from docker.src.websocket_server import EnhancedSTTWebSocketServer

        print("✅ WebSocket server imports successful")

        # Test server launcher imports
        from docker.src.server_launcher import DockerServerLauncher

        print("✅ Server launcher imports successful")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_token_manager():
    """Test token manager functionality"""
    print("\n🔍 Testing token manager...")

    try:
        # Create temporary test directory
        test_dir = Path("/tmp/stt_test")
        test_dir.mkdir(exist_ok=True)

        # Initialize token manager
        from docker.src.token_manager import TokenManager

        token_manager = TokenManager(data_dir=test_dir)

        # Test token generation
        token_data = token_manager.generate_token("test_client", 30, one_time_use=True)
        print(f"✅ Generated token: {token_data['token_id']}")

        # Test token validation
        payload = token_manager.validate_token(token_data["token"])
        if payload:
            print("✅ Token validation successful")
        else:
            print("❌ Token validation failed")
            return False

        # Test one-time use enforcement
        payload2 = token_manager.validate_token(token_data["token"], mark_as_used=True)
        payload3 = token_manager.validate_token(token_data["token"], mark_as_used=True)

        if payload2 and not payload3:
            print("✅ One-time use enforcement working")
        else:
            print("❌ One-time use enforcement failed")
            return False

        # Cleanup
        import shutil

        shutil.rmtree(test_dir, ignore_errors=True)

        return True

    except Exception as e:
        print(f"❌ Token manager test failed: {e}")
        return False


def test_encryption():
    """Test encryption functionality"""
    print("\n🔍 Testing encryption...")

    try:
        # Create temporary test directory
        test_dir = Path("/tmp/stt_encryption_test")
        test_dir.mkdir(exist_ok=True)

        # Initialize encryption manager
        from docker.src.encryption import EncryptionManager

        encryption_manager = EncryptionManager(test_dir)

        # Test key generation
        public_key = encryption_manager.get_public_key_pem()
        if public_key and "BEGIN PUBLIC KEY" in public_key:
            print("✅ RSA key generation successful")
        else:
            print("❌ RSA key generation failed")
            return False

        # Cleanup
        import shutil

        shutil.rmtree(test_dir, ignore_errors=True)

        return True

    except Exception as e:
        print(f"❌ Encryption test failed: {e}")
        return False


def test_dashboard_api():
    """Test dashboard API creation"""
    print("\n🔍 Testing dashboard API...")

    try:
        # Mock the data directory
        os.environ["STT_DOCKER_MODE"] = "1"

        from docker.src.api import DashboardAPI

        api = DashboardAPI()

        if api.app and api.token_manager:
            print("✅ Dashboard API initialization successful")
            return True
        print("❌ Dashboard API initialization failed")
        return False

    except Exception as e:
        print(f"❌ Dashboard API test failed: {e}")
        return False


def main():
    """Run all validation tests"""
    print("🐳 STT Docker Server Validation\n")

    tests = [
        ("Import Tests", test_imports),
        ("Token Manager", test_token_manager),
        ("Encryption", test_encryption),
        ("Dashboard API", test_dashboard_api),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print("=" * 50)

        try:
            if test_func():
                print(f"✅ {test_name} PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} FAILED")
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print("VALIDATION SUMMARY")
    print("=" * 50)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")

    if failed == 0:
        print("\n🎉 All validation tests passed! Docker server is ready for deployment.")
        return 0
    print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
