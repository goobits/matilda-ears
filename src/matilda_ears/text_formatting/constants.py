#!/usr/bin/env python3
"""Shared constants for text formatting modules."""

import json
import os
import threading
from typing import Any

# ==============================================================================
# I18N RESOURCE LOADER
# ==============================================================================

_RESOURCES: dict[str, dict[str, Any]] = {}  # Cache for loaded languages
_RESOURCE_PATH = os.path.join(os.path.dirname(__file__), "resources")
_LOCK = threading.Lock()  # For thread-safe lazy loading


def get_resources(language: str = "en") -> dict[str, Any]:
    """Loads and caches language-specific resources from a JSON file.
    This is the single point of entry for all language-dependent constants.

    Args:
        language: Language code (e.g., 'en', 'es', 'fr')

    Returns:
        dict: Loaded language resources

    Raises:
        ValueError: If default language resource not found

    """
    # Return from cache if already loaded
    if language in _RESOURCES:
        return _RESOURCES[language]

    # Thread-safe block to load a new language
    with _LOCK:
        # Double-check if another thread loaded it while we were waiting
        if language in _RESOURCES:
            return _RESOURCES[language]

        try:
            filepath = os.path.join(_RESOURCE_PATH, f"{language}.json")
            with open(filepath, encoding="utf-8") as f:
                resources: dict[str, Any] = json.load(f)
                _RESOURCES[language] = resources
            return resources
        except FileNotFoundError:
            # Fallback to English if the requested language is not found
            if language != "en":
                print(f"Warning: Language resource '{language}.json' not found. Falling back to 'en'.")
                return get_resources("en")
            raise ValueError("Default language resource 'en.json' not found.")
        except json.JSONDecodeError:
            raise ValueError(f"Error decoding JSON from {language}.json")


