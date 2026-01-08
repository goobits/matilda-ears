#!/usr/bin/env python3
"""Circuit breaker implementation for WebSocket connection resilience.

This module provides a lightweight circuit breaker pattern for managing
WebSocket connections with automatic recovery.
"""

import time
from enum import Enum
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable


class CircuitState(Enum):
    """States of the circuit breaker."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 3  # Failures before opening
    timeout_seconds: int = 30  # How long to stay open
    success_threshold: int = 2  # Successes needed to close from half-open


class CircuitBreaker:
    """Lightweight circuit breaker for WebSocket connections."""

    def __init__(self, config_obj: CircuitBreakerConfig | None = None):
        """Initialize circuit breaker.

        Args:
            config_obj: Circuit breaker configuration (uses defaults if not provided)

        """
        self.config = config_obj or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0

    def can_execute(self) -> bool:
        """Check if operation should be allowed.

        Returns:
            True if operation should proceed, False if circuit is open

        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if time.time() - self.last_failure_time >= self.config.timeout_seconds:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return True
            return False

        # HALF_OPEN state - allow limited requests
        return True

    def record_success(self):
        """Record successful operation."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0

        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0  # Reset on success

    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN

        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0

    def execute(self, func: Callable[[], Any]) -> tuple[bool, Any, str | None]:
        """Execute function with circuit breaker protection.

        Args:
            func: Function to execute

        Returns:
            (success: bool, result: Any, error_message: Optional[str])

        """
        if not self.can_execute():
            return False, None, f"Circuit breaker is {self.state.value}"

        try:
            result = func()
            self.record_success()
            return True, result, None
        except Exception as e:
            self.record_failure()
            return False, None, str(e)

    def get_status(self) -> dict:
        """Get current circuit breaker status for monitoring.

        Returns:
            Dictionary with circuit breaker state information

        """
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "can_execute": self.can_execute(),
        }
