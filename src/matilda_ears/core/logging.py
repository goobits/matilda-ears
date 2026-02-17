"""Centralized logging setup for Matilda Ears.

This module provides standardized logging configuration for all STT modules.
"""

import atexit
import logging
import os
import sys
import threading
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from queue import SimpleQueue

_LISTENER_LOCK = threading.Lock()
_LOG_QUEUE: SimpleQueue | None = None
_LOG_LISTENER: QueueListener | None = None


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes"}


def _stop_listener() -> None:
    global _LOG_LISTENER
    if _LOG_LISTENER is not None:
        _LOG_LISTENER.stop()
        _LOG_LISTENER = None


def _resolve_logs_dir() -> Path | None:
    env_dir = os.environ.get("MATILDA_LOG_DIR") or os.environ.get("MATILDA_EARS_LOG_DIR")
    if env_dir:
        logs_dir = Path(env_dir)
    else:
        logs_dir = Path.home() / ".matilda" / "logs"

    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return logs_dir


def _ensure_listener(log_level: int, include_console: bool, include_file: bool) -> QueueListener | None:
    global _LOG_QUEUE, _LOG_LISTENER
    with _LISTENER_LOCK:
        if _LOG_LISTENER is not None and _LOG_QUEUE is not None:
            return _LOG_LISTENER

        handlers: list[logging.Handler] = []
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        if include_file:
            logs_dir = _resolve_logs_dir()
            if logs_dir is not None:
                log_filename = os.environ.get("MATILDA_EARS_LOG_FILE", "matilda-ears.log")
                log_path = logs_dir / log_filename
                try:
                    max_bytes = int(os.environ.get("MATILDA_LOG_MAX_BYTES", "10485760"))
                except ValueError:
                    max_bytes = 10 * 1024 * 1024
                try:
                    backup_count = int(os.environ.get("MATILDA_LOG_BACKUP_COUNT", "5"))
                except ValueError:
                    backup_count = 5
                try:
                    file_handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count)
                except OSError:
                    file_handler = None
                if file_handler is not None:
                    file_handler.setLevel(log_level)
                    file_handler.setFormatter(formatter)
                    handlers.append(file_handler)

        if include_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            handlers.append(console_handler)

        if not handlers:
            return None

        _LOG_QUEUE = SimpleQueue()
        _LOG_LISTENER = QueueListener(_LOG_QUEUE, *handlers, respect_handler_level=True)
        _LOG_LISTENER.start()
        atexit.register(_stop_listener)
        return _LOG_LISTENER


def setup_logging(
    module_name: str,
    log_level: str = "INFO",
    include_console: bool | None = None,
    include_file: bool = True,
    log_filename: str | None = None,
) -> logging.Logger:
    """Setup standardized logging for STT modules.

    Args:
        module_name: Name of the module (usually __name__)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        include_console: Whether to log to console. If None, uses
            MATILDA_EARS_CONSOLE_LOGS ("1"/"true"/"yes" enables).
        include_file: Whether to log to file
        log_filename: Optional custom log filename (defaults to module-based name)

    Returns:
        Configured logger instance

    """
    logger = logging.getLogger(module_name)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    level = getattr(logging, log_level.upper())
    logger.setLevel(level)
    if include_console is None:
        include_console = _is_truthy(os.environ.get("MATILDA_EARS_CONSOLE_LOGS"))

    # Prevent propagation to root logger to avoid duplicate console output
    logger.propagate = False
    # log_filename is intentionally not used in unified mode; all modules go to one sink.
    _ = log_filename

    listener = _ensure_listener(level, include_console, include_file)
    if listener is None or _LOG_QUEUE is None:
        logger.addHandler(logging.NullHandler())
        return logger

    queue_handler = QueueHandler(_LOG_QUEUE)
    queue_handler.setLevel(level)
    logger.addHandler(queue_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """Get a logger for a module with default STT settings."""
    return setup_logging(module_name)


__all__ = ["setup_logging", "get_logger"]
