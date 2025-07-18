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
    print("🔍 Verifying GOOBITS STT test setup dependencies...\n")

    dependencies = [
        # Core testing
        ("pytest", "Testing framework", False),
        ("xdist", "Parallel test execution", False),
        # STT dependencies (required for text formatting tests)
        ("spacy", "SpaCy NLP library", False),
        ("pyparsing", "Text parsing library", False),
        ("faster_whisper", "Whisper transcription", False),
        ("torch", "PyTorch ML framework", False),
        ("torchaudio", "PyTorch audio processing", False),
        ("deepmultilingualpunctuation", "Punctuation restoration", False),
        # Audio dependencies
        ("opuslib", "Opus audio codec", False),
        ("silero_vad", "Voice activity detection", False),
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
        ("pynput", "Keyboard/mouse input", False),
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
    print('   pip install -e ".[dev]"')
    if any("opus" in str(dep[0]).lower() for dep in dependencies):
        print("\nFor system dependencies like Opus:")
        print("   # Ubuntu/Debian:")
        print("   sudo apt-get install libopus-dev libopus0")
        print("   # macOS:")
        print("   brew install opus")
    return 1


if __name__ == "__main__":
    sys.exit(main())
