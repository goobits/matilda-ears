"""
Hook implementations for Matilda Ears - Speech-to-Text Engine.

This file proxies to the actual implementations in matilda_ears.app_hooks.
"""

# Re-export all hooks from the main app_hooks module
from matilda_ears.app_hooks import (
    on_transcribe,
    on_status,
    on_models,
)

__all__ = [
    "on_transcribe",
    "on_status",
    "on_models",
]
