"""Centralized authentication policy for matilda-ears.

Single source of truth for all auth decisions. Handlers call auth.check()
instead of duplicating auth logic.
"""

import logging
import os
from ipaddress import ip_address
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .token_manager import TokenManager

logger = logging.getLogger(__name__)


@dataclass
class AuthResult:
    """Result of an authentication check."""

    authorized: bool
    client_id: str | None = None
    method: str | None = None  # jwt, dev_token, localhost, dev_mode


class AuthPolicy:
    """Centralized auth policy - one place to change.

    Auth methods (checked in order):
        1. Valid JWT token (production)
        2. Dev token from orchestrator (local dev)
        3. Localhost connection (127.0.0.1, ::1)
        4. Explicit dev mode env var

    Example::

        result = server.auth.check(token, client_ip)
        if not result.authorized:
            await send_error(websocket, "Authentication required")

    """

    def __init__(self, token_manager: "TokenManager"):
        self.token_manager = token_manager
        self._dev_token = os.getenv("STT_DEV_TOKEN")
        self._dev_mode = os.getenv("STT_DEV_MODE", "").lower() in ("1", "true")
        self._allow_token_generation = os.getenv("STT_ALLOW_TOKEN_GENERATION", "").lower() in ("1", "true")

        if self._dev_token:
            logger.info("Dev token configured (from orchestrator)")
        if self._dev_mode:
            logger.info("Dev mode enabled (STT_DEV_MODE=true)")

    def check(
        self,
        token: str | None,
        client_ip: str,
    ) -> AuthResult:
        """Single auth check - used by all handlers.

        Args:
            token: JWT or dev token from request
            client_ip: Client IP address
        Returns:
            AuthResult with authorized status and method used

        """
        # 1. Dev token from orchestrator (local development)
        if token and self._dev_token and token == self._dev_token:
            return AuthResult(authorized=True, client_id=f"dev:{client_ip}", method="dev_token")

        # 2. Valid JWT token (production path)
        if token:
            payload = self.token_manager.validate_token(token)
            if payload:
                client_id = payload.get("client_name") or payload.get("token_id") or "jwt_client"
                return AuthResult(authorized=True, client_id=str(client_id), method="jwt")

        # 3. Loopback transport
        if self._is_localhost(client_ip):
            return AuthResult(authorized=True, client_id=f"local:{client_ip}", method="localhost")

        # 4. Explicit dev mode (escape hatch)
        if self._dev_mode:
            return AuthResult(authorized=True, client_id=f"dev_mode:{client_ip}", method="dev_mode")

        # 5. Deny
        return AuthResult(authorized=False)

    def can_generate_tokens(self, client_ip: str) -> bool:
        """Check if token generation is allowed.

        Token generation is sensitive (creates long-lived JWTs).
        Only allowed for localhost or explicit env var.
        """
        if self._allow_token_generation:
            return True
        if self._is_localhost(client_ip):
            return True
        if self._dev_mode:
            return True
        return False

    def _is_localhost(self, ip: str) -> bool:
        """Check if IP is localhost."""
        if ip == "localhost":
            return True
        try:
            address = ip_address(ip.split("%", maxsplit=1)[0])
        except ValueError:
            return False
        if address.is_loopback:
            return True
        mapped = getattr(address, "ipv4_mapped", None)
        return bool(mapped and mapped.is_loopback)
