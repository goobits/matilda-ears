"""Centralized logging setup for Matilda Ears.

This module provides standardized logging configuration for all STT modules.
"""

import logging
import sys
from pathlib import Path


def setup_logging(
    module_name: str,
    log_level: str = "INFO",
    include_console: bool = True,
    include_file: bool = True,
    log_filename: str | None = None,
) -> logging.Logger:
    """Setup standardized logging for STT modules.

    Args:
        module_name: Name of the module (usually __name__)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        include_console: Whether to log to console
        include_file: Whether to log to file
        log_filename: Optional custom log filename (defaults to module-based name)

    Returns:
        Configured logger instance

    """
    logger = logging.getLogger(module_name)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, log_level.upper()))

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    if include_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Prevent propagation to root logger to avoid duplicate console output
    logger.propagate = False

    # File handler
    if include_file:
        # Import here to avoid circular imports
        from .config import get_config

        # Ensure logs directory exists
        logs_dir = Path(get_config().project_dir) / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Generate log filename
        if log_filename is None:
            module_basename = module_name.split(".")[-1] if "." in module_name else module_name
            log_filename = f"{module_basename}.txt"

        log_path = logs_dir / log_filename
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """Get a logger for a module with default STT settings."""
    return setup_logging(module_name)


__all__ = ["setup_logging", "get_logger"]
