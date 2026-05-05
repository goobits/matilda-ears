"""Process memory helpers."""

from __future__ import annotations

import os
import re
import resource
import subprocess

_SIZE_RE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[KMGT]?B?)", re.IGNORECASE)


def _size_to_bytes(text: str) -> int | None:
    match = _SIZE_RE.search(text)
    if match is None:
        return None
    value = float(match.group("value"))
    unit = match.group("unit").upper()
    if unit in {"K", "M", "G", "T"}:
        unit = f"{unit}B"
    multiplier = {
        "B": 1,
        "KB": 1024,
        "MB": 1024**2,
        "GB": 1024**3,
        "TB": 1024**4,
    }.get(unit)
    return None if multiplier is None else int(value * multiplier)


def current_rss_bytes() -> int | None:
    """Return current process RSS in bytes when available."""
    try:
        import psutil

        return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        pass

    try:
        with open("/proc/self/statm", encoding="utf-8") as f:
            pages = int(f.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        pass

    try:
        output = subprocess.check_output(
            ["ps", "-o", "rss=", "-p", str(os.getpid())],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1,
        )
        return int(output.strip()) * 1024
    except Exception:
        return None


def peak_rss_bytes() -> int | None:
    """Return peak process RSS in bytes when available."""
    try:
        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except Exception:
        return None

    if value <= 0:
        return None
    if os.uname().sysname == "Darwin":
        return value
    return value * 1024


def macos_footprint_summary() -> dict[str, int]:
    """Return expensive macOS footprint counters for manual diagnostics."""
    try:
        if os.uname().sysname != "Darwin":
            return {}
    except Exception:
        return {}

    try:
        output = subprocess.check_output(
            ["footprint", "-p", str(os.getpid()), "-summary"],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        )
    except Exception:
        return {}

    result: dict[str, int] = {}
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("phys_footprint:"):
            value = _size_to_bytes(stripped)
            if value is not None:
                result["physical_footprint_bytes"] = value
        elif stripped.endswith("IOAccelerator (graphics)") or "IOAccelerator (graphics)" in stripped:
            value = _size_to_bytes(stripped)
            if value is not None:
                result["ioaccelerator_graphics_bytes"] = value
        elif stripped.endswith("IOAccelerator") or "IOAccelerator" in stripped:
            value = _size_to_bytes(stripped)
            if value is not None and "ioaccelerator_graphics_bytes" not in result:
                result["ioaccelerator_bytes"] = value

    return result
