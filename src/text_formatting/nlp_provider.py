"""Shared NLP model provider to eliminate circular imports.

This module provides centralized access to the SpaCy NLP model
and other AI models used by the text formatting system.
"""

import os
import threading
from ..core.config import setup_logging

logger = setup_logging(__name__, log_filename="text_formatting.txt")

# Global model instances with thread-safe lazy loading
_nlp = None
_punctuator = None
_models_lock = threading.Lock()


def get_nlp():
    """Lazy-load SpaCy model with thread-safe singleton pattern.

    Returns:
        Optional: SpaCy NLP model instance or None if loading failed

    """
    global _nlp
    if _nlp is None:
        with _models_lock:
            if _nlp is None:
                try:
                    import spacy
                    import sysconfig
                    from pathlib import Path

                    # First try loading by name
                    try:
                        _nlp = spacy.load("en_core_web_sm", disable=["senter"])
                        logger.info("SpaCy model loaded successfully (optimized: senter disabled)")
                    except (OSError, ValueError):
                        # Fallback: try loading from site-packages path (for minimal/testing models)
                        site_packages = Path(sysconfig.get_path('purelib'))
                        model_path = site_packages / 'en_core_web_sm'
                        if model_path.exists():
                            _nlp = spacy.load(str(model_path), disable=["senter"])
                            logger.info(f"SpaCy model loaded from path: {model_path}")
                        else:
                            raise OSError(f"Model not found by name or at path: {model_path}")
                except (ImportError, OSError, ValueError) as e:
                    logger.warning(f"Failed to load SpaCy model: {e}")
                    _nlp = False
    return _nlp if _nlp else None


def get_punctuator():
    """Lazy-load punctuation model with thread-safe singleton pattern.

    Returns:
        Optional: Punctuation model instance or None if loading failed

    """
    global _punctuator

    # Check for no-punctuation mode first
    if os.environ.get("STT_DISABLE_PUNCTUATION") == "1":
        # Return a simple no-op function that does nothing
        class NoopPunctuator:
            def restore_punctuation(self, text, **kwargs):
                return text

        if _punctuator is None:
            logger.info("✅ FORMATTER SUCCESS: Punctuator is DISABLED for testing.")
        return NoopPunctuator()

    if _punctuator is None:
        with _models_lock:
            if _punctuator is None:
                try:
                    from deepmultilingualpunctuation import PunctuationModel

                    _punctuator = PunctuationModel()
                    logger.info("✅ FORMATTER SUCCESS: Text formatter loaded (deepmultilingualpunctuation)")
                except ImportError:
                    logger.warning("❌ FORMATTER IMPORT FAILED: deepmultilingualpunctuation not found in this context")
                    _punctuator = False
                except (ImportError, OSError, ValueError, RuntimeError) as e:
                    logger.error(f"❌ FORMATTER MODEL LOAD FAILED: {e}", exc_info=True)
                    _punctuator = False
    return _punctuator if _punctuator else None


def reset_models():
    """Reset loaded models (useful for testing)."""
    global _nlp, _punctuator
    with _models_lock:
        _nlp = None
        _punctuator = None
