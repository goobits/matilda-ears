"""Resolve opuslib against an explicitly managed native library."""

from __future__ import annotations

import ctypes.util
import importlib
import os
from pathlib import Path
from types import ModuleType


def _load_opuslib() -> ModuleType:
    configured = os.getenv("MATILDA_OPUS_LIBRARY", "").strip()
    if not configured:
        return importlib.import_module("opuslib")

    library = Path(configured).expanduser()
    if not library.is_file():
        raise RuntimeError(f"MATILDA_OPUS_LIBRARY does not exist: {library}")

    find_library = ctypes.util.find_library
    ctypes.util.find_library = lambda name: str(library) if name == "opus" else find_library(name)
    try:
        return importlib.import_module("opuslib")
    finally:
        ctypes.util.find_library = find_library


opuslib = _load_opuslib()
