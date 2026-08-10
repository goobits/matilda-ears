#!/usr/bin/env python3
"""Verify required and optional Matilda Ears test dependencies."""

from __future__ import annotations

import importlib

REQUIRED = {
    "aiohttp": "HTTP client",
    "bandit": "security scanner",
    "black": "formatter",
    "cryptography": "TLS support",
    "matilda_transport": "shared transport",
    "mypy": "type checker",
    "numpy": "audio arrays",
    "opuslib": "Opus codec",
    "pytest": "test runner",
    "pytest_cov": "coverage plugin",
    "ruff": "linter",
    "websockets": "WebSocket support",
    "xdist": "parallel tests",
}

OPTIONAL = {
    "faster_whisper": "Whisper backend",
    "mlx": "Apple MLX runtime",
    "openwakeword": "wake-word backend",
    "parakeet_mlx": "Parakeet backend",
    "silero_vad": "voice activity detection",
    "torch": "streaming runtime",
}


def _available(module: str) -> bool:
    try:
        importlib.import_module(module)
    except Exception:
        return False
    return True


def main() -> int:
    missing = []
    for module, purpose in REQUIRED.items():
        if _available(module):
            print(f"✅ {purpose}: {module}")
        else:
            print(f"❌ {purpose}: {module}")
            missing.append(module)

    for module, purpose in OPTIONAL.items():
        symbol = "✅" if _available(module) else "➖"
        print(f"{symbol} optional {purpose}: {module}")

    if missing:
        print(f"\nMissing required dependencies: {', '.join(missing)}")
        return 1
    print("\nAll required test dependencies are available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
