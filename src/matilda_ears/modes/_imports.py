#!/usr/bin/env python3
"""Shared imports and fallbacks for mode modules.

This module centralizes common imports and fallback definitions
to avoid duplication across mode files.

Usage:
    from ._imports import np, NUMPY_AVAILABLE, keyboard, PYNPUT_AVAILABLE
"""

import sys
from pathlib import Path

# Add project root to path for local imports (only once)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# NumPy fallback for type annotations
# =============================================================================

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

    class _DummyNumpy:
        """Dummy numpy module for type annotations when numpy is not available."""

        class ndarray:
            pass

        def concatenate(self, *args, **kwargs):
            raise ImportError("NumPy is required for this operation")

    np = _DummyNumpy()  # type: ignore[assignment]

# =============================================================================
# Pynput keyboard fallback
# =============================================================================

try:
    from pynput import keyboard
    from pynput.keyboard import Controller, Key, Listener

    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    keyboard = None  # type: ignore[assignment]
    Controller = None  # type: ignore[assignment]
    Key = None  # type: ignore[assignment]
    Listener = None  # type: ignore[assignment]

# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Standard library
    "sys",
    # NumPy
    "np",
    "NUMPY_AVAILABLE",
    # Pynput
    "keyboard",
    "Controller",
    "Key",
    "Listener",
    "PYNPUT_AVAILABLE",
]
