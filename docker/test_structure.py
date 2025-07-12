#!/usr/bin/env python3
"""Quick structure test for the Docker Matilda server
Tests basic imports and structure without external dependencies
"""

import sys
from pathlib import Path

# Add workspace to path
sys.path.append("/workspace")


def test_structure():
    """Test the new file structure"""
    print("🔍 Testing Docker folder structure...")

    docker_dir = Path("/workspace/docker")

    # Check main directories exist
    required_dirs = ["src", "dashboard"]
    for dir_name in required_dirs:
        dir_path = docker_dir / dir_name
        if dir_path.exists():
            print(f"✅ {dir_name}/ directory exists")
        else:
            print(f"❌ {dir_name}/ directory missing")
            return False

    # Check core Python files exist
    required_files = [
        "src/__init__.py",
        "src/api.py",
        "src/encryption.py",
        "src/token_manager.py",
        "src/websocket_server.py",
        "src/server_launcher.py",
        "src/validate_setup.py",
    ]

    for file_path in required_files:
        full_path = docker_dir / file_path
        if full_path.exists():
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} missing")
            return False

    # Check dashboard files exist
    dashboard_files = ["dashboard/index.html", "dashboard/dashboard.js", "dashboard/admin.css"]

    for file_path in dashboard_files:
        full_path = docker_dir / file_path
        if full_path.exists():
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} missing")
            return False

    # Check Docker files exist
    docker_files = ["Dockerfile", "docker-compose.yml", "README.md"]
    for file_name in docker_files:
        file_path = docker_dir / file_name
        if file_path.exists():
            print(f"✅ {file_name} exists")
        else:
            print(f"❌ {file_name} missing")
            return False

    print("\n✅ All required files and directories are present!")
    return True


def test_basic_imports():
    """Test basic imports that don't require external dependencies"""
    print("\n🔍 Testing basic imports...")

    try:
        # Test core components that don't need FastAPI
        from docker.src.encryption import EncryptionManager

        print("✅ EncryptionManager import successful")

        from docker.src.token_manager import TokenManager

        print("✅ TokenManager import successful")

        # Test package structure
        import docker.src

        print("✅ Package structure working")

        return True

    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Run structure tests"""
    print("🐳 Docker Matilda Server Structure Test\n")

    structure_ok = test_structure()
    imports_ok = test_basic_imports()

    if structure_ok and imports_ok:
        print("\n🎉 Structure test PASSED - Docker setup is properly organized!")
        return 0
    print("\n❌ Structure test FAILED - Please check the issues above")
    return 1


if __name__ == "__main__":
    sys.exit(main())
