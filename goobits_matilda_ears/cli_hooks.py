"""
Bridge module for Matilda Ears CLI hooks.

This module bridges the generated CLI to the real hook implementations
in matilda_ears.app_hooks.
"""

# Import all hooks from the real implementation
from matilda_ears.app_hooks import (
    on_status,
    on_models,
    on_transcribe,
)

# Re-export for the generated CLI
__all__ = ["on_status", "on_models", "on_transcribe"]
