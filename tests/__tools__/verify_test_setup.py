#!/usr/bin/env python3
"""Verification script to check if all test dependencies are properly installed.
Run this before running the test suite to ensure everything is set up correctly.
"""

import sys
import importlib


def check_dependency(module_name, description, allow_display_errors=False):
    """Check if a dependency can be imported"""
    try:
        importlib.import_module(module_name)
        print(f"✅ {description}: {module_name}")
        return True
    except ImportError as e:
        print(f"❌ {description}: {module_name} - {e}")
        return False
    except Exception as e:
        error_str = str(e).lower()
        if allow_display_errors and any(
            keyword in error_str for keyword in ["display", "x server", "egl", "connection refused", "x11"]
        ):
            print(f"⚠️  {description}: {module_name} - Display/Graphics not available (OK for headless)")
            return True
        print(f"❌ {description}: {module_name} - {e}")
        return False


def main():
    """Check all test dependencies"""
    print("🔍 Verifying test setup dependencies...\n")

    dependencies = [
        # Core testing
        ("pytest", "Testing framework", False),
        ("xdist", "Parallel test execution", False),  # Fixed: xdist not pytest_xdist
        # Server dependencies (required for text formatting tests)
        ("spacy", "SpaCy NLP library", False),
        ("pyparsing", "Text parsing library", False),
        ("faster_whisper", "Whisper transcription", False),
        ("torch", "PyTorch ML framework", False),
        # Visualizer dependencies (required for audio tests)
        ("opuslib", "Opus audio codec", False),
        ("PIL", "Pillow image library", False),
        # Development tools
        ("ruff", "Code linting", False),
        ("black", "Code formatting", False),
        ("mypy", "Type checking", False),
        ("bandit", "Security scanning", False),
        # Core dependencies
        ("numpy", "Numerical computing", False),
        ("websockets", "WebSocket support", False),
        ("aiohttp", "Async HTTP client", False),
        ("cryptography", "Cryptographic functions", False),
        ("requests", "HTTP requests", False),
    ]

    passed = 0
    failed = 0

    for module, description, allow_display_errors in dependencies:
        if check_dependency(module, description, allow_display_errors):
            passed += 1
        else:
            failed += 1

    print(f"\n📊 Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("\n🎉 All dependencies verified! You're ready to run tests.")
        print("   Run: ./test.py tests/text_formatting/ --track-diff")
        return 0
    print(f"\n⚠️  {failed} dependencies missing. Install with:")
    print('   pip install -e ".[dev,server,visualizer]"')
    if any("opus" in str(dep[0]).lower() for dep in dependencies):
        print("\nFor system dependencies like Opus:")
        print("   python scripts/install_system_deps.py  # Interactive")
        print("   python scripts/install_system_deps.py --auto  # Auto-install")
        print("   # Or manually:")
        print("   sudo apt-get install libopus-dev libopus0  # Ubuntu/Debian")
    return 1


if __name__ == "__main__":
    sys.exit(main())
