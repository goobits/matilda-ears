"""STT Docker Server Source Code

This package contains the core components for the STT Docker server:
- Admin dashboard API
- End-to-end encryption
- JWT token management
- Enhanced WebSocket server
- Server launcher and coordination
"""

from pathlib import Path
import tomllib


def _get_version() -> str:
    try:
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return str(data["project"]["version"])
    except Exception:
        return "unknown"


__version__ = _get_version()
__author__ = "STT Team"
