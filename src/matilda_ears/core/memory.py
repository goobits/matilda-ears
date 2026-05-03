"""Process memory helpers."""

from __future__ import annotations

import os
import resource
import subprocess


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
