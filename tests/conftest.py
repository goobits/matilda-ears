"""Shared pytest configuration for Matilda Ears."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for path in (PROJECT_ROOT / "src", PROJECT_ROOT):
    sys.path.insert(0, str(path))

pythonpath = os.pathsep.join((str(PROJECT_ROOT / "src"), str(PROJECT_ROOT)))
if existing := os.environ.get("PYTHONPATH"):
    pythonpath = f"{pythonpath}{os.pathsep}{existing}"
os.environ["PYTHONPATH"] = pythonpath

pytest_plugins = ["tests.__tools__.pytest_diff_tracker", "tests.__tools__.pytest_summary_plugin"]
logging.getLogger("matilda_ears.core").setLevel(logging.CRITICAL)


@pytest.fixture(scope="session", autouse=True)
def shared_config_env():
    """Point tests at the repository's shared Matilda configuration."""
    previous = os.environ.get("MATILDA_CONFIG")
    config_path = PROJECT_ROOT.parent / "matilda" / "config.toml"
    os.environ.setdefault("MATILDA_CONFIG", str(config_path))
    yield config_path
    if previous is None:
        os.environ.pop("MATILDA_CONFIG", None)
    else:
        os.environ["MATILDA_CONFIG"] = previous


def _parakeet_available() -> bool:
    try:
        import mlx.core  # noqa: F401
        import parakeet_mlx  # noqa: F401
    except Exception:
        return False
    return True


def pytest_collection_modifyitems(items):
    if _parakeet_available():
        return
    skip = pytest.mark.skip(reason="Parakeet MLX backend not available")
    for item in items:
        if "test_parakeet_backend" in item.nodeid:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def preloaded_config():
    """Load the shared configuration once for smoke tests."""
    try:
        from matilda_ears.core.config import get_config
    except ImportError:
        return None
    return get_config()
