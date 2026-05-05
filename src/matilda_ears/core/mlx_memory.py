"""MLX memory helpers."""

from __future__ import annotations

import gc
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def _call_int(fn: Callable[[], Any] | None) -> int | None:
    if fn is None:
        return None
    try:
        value = fn()
    except Exception:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def mlx_memory_stats() -> dict[str, int | None]:
    """Return MLX Metal memory counters when the active MLX version exposes them."""
    try:
        import mlx.core as mx
    except Exception:
        return {}

    metal = getattr(mx, "metal", None)

    stats = {
        "active_bytes": _call_int(
            getattr(mx, "get_active_memory", None)
            or (getattr(metal, "get_active_memory", None) if metal is not None else None)
        ),
        "cache_bytes": _call_int(
            getattr(mx, "get_cache_memory", None)
            or (getattr(metal, "get_cache_memory", None) if metal is not None else None)
        ),
        "peak_bytes": _call_int(
            getattr(mx, "get_peak_memory", None)
            or (getattr(metal, "get_peak_memory", None) if metal is not None else None)
        ),
    }
    return {key: value for key, value in stats.items() if value is not None}


def clear_mlx_cache() -> bool:
    """Ask MLX to release cached Metal allocations."""
    released = False
    gc.collect()
    try:
        import mlx.core as mx
    except Exception:
        return released

    clear_cache = getattr(mx, "clear_cache", None)
    if clear_cache is None:
        metal = getattr(mx, "metal", None)
        clear_cache = getattr(metal, "clear_cache", None) if metal is not None else None
    if clear_cache is None:
        return released

    try:
        clear_cache()
        released = True
    except Exception as e:
        logger.debug("MLX cache cleanup failed: %s", e)
    return released
