"""Pytest configuration for integration tests.

Mocks external dependencies to allow testing without actual model installations.
"""

import sys
import os
from unittest.mock import MagicMock

# Set environment variable to bypass server startup check
os.environ["MATILDA_MANAGEMENT_TOKEN"] = "managed-by-matilda-system"


def _install_integration_mocks() -> None:
    # Mock external dependencies before ANY imports
    sys.modules["faster_whisper"] = MagicMock()
    sys.modules["numpy"] = MagicMock()
    sys.modules["opuslib"] = MagicMock()
    sys.modules["websockets"] = MagicMock()

    # Mock MLX and Parakeet for Apple Silicon backend testing
    sys.modules["mlx"] = MagicMock()
    sys.modules["mlx.core"] = MagicMock()
    sys.modules["parakeet_mlx"] = MagicMock()

    # Mock missing token_manager module
    sys.modules["matilda_ears.core.token_manager"] = MagicMock()


if os.environ.get("MATILDA_INTEGRATION_MOCKS") == "1":
    _install_integration_mocks()

# Also mock pytest-asyncio if not installed
import importlib.util

if importlib.util.find_spec("pytest_asyncio") is None:
    # Create a simple mock for asyncio marker if pytest-asyncio is not installed

    # Register the asyncio marker to avoid warnings
    def pytest_configure(config):
        config.addinivalue_line("markers", "asyncio: mark test as an asyncio test")
