"""
Shared NLP model provider to eliminate circular imports.

This module provides centralized access to the SpaCy NLP model
and other AI models used by the text formatting system.

SpaCy is now a hard dependency - the system will fail-fast if SpaCy
or required models are not available, ensuring predictable behavior.
"""

import os
import sys
import threading

from stt.core.config import setup_logging

logger = setup_logging(__name__, log_filename="text_formatting.txt", include_console=False)

# Global model instances with thread-safe lazy loading
_nlp = None
_punctuator = None
_models_lock = threading.Lock()


def _validate_spacy_installation():
    """
    Validate that SpaCy and required models are properly installed.
    
    This performs startup validation to ensure all required dependencies
    are available before attempting to use them.
    
    Raises:
        SystemExit: If SpaCy or required models are not available
    """
    try:
        import spacy
    except ImportError as e:
        logger.error(
            "SpaCy is required but not installed. "
            "Install with: pip install spacy"
        )
        sys.exit(1)
    
    try:
        # Test model loading
        spacy.load("en_core_web_sm")
    except (OSError, IOError) as e:
        logger.error(
            "SpaCy model 'en_core_web_sm' is required but not installed. "
            "Install with: python -m spacy download en_core_web_sm"
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to validate SpaCy model: {e}")
        sys.exit(1)


def get_nlp():
    """
    Load SpaCy model with thread-safe singleton pattern.

    Returns:
        spacy.Language: SpaCy NLP model instance

    Raises:
        SystemExit: If SpaCy model cannot be loaded
    """
    global _nlp
    if _nlp is None:
        with _models_lock:
            if _nlp is None:
                _validate_spacy_installation()
                
                try:
                    import spacy
                    _nlp = spacy.load("en_core_web_sm", disable=["senter"])
                    logger.info("SpaCy model loaded successfully (optimized: senter disabled)")
                except Exception as e:
                    logger.error(f"Critical error loading SpaCy model: {e}")
                    sys.exit(1)
                    
    return _nlp


def get_punctuator():
    """
    Lazy-load punctuation model with thread-safe singleton pattern.

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
    """
    Reset loaded models (useful for testing).
    
    Note: After reset, next call to get_nlp() will perform full validation
    and fail-fast if dependencies are not available.
    """
    global _nlp, _punctuator
    with _models_lock:
        _nlp = None
        _punctuator = None
