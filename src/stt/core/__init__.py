"""
Core package for GOOBITS STT - Essential components for configuration, logging, and system management.

This package provides:
- ConfigLoader: Configuration management with JSONC support
- ModelManager: Singleton Whisper model caching and management
- TokenManager: JWT token generation and validation
- TokenBucketRateLimiter: Advanced rate limiting with burst protection
- StructuredFormatter: JSON/readable logging formatter
"""

from .config import ConfigLoader, ConfigurationError
from .logging import StructuredFormatter, setup_structured_logging, get_logger, set_context, clear_context
from .model_manager import ModelManager
from .rate_limiter import TokenBucketRateLimiter
from .token_manager import TokenManager

__all__ = [
    "ConfigLoader",
    "ConfigurationError", 
    "ModelManager",
    "TokenManager",
    "TokenBucketRateLimiter",
    "StructuredFormatter",
    "setup_structured_logging",
    "get_logger",
    "set_context",
    "clear_context",
]