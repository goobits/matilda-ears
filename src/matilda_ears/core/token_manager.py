"""JWT token generation, validation, and replay protection."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt

from .token_store import TokenStore, TokenStoreError, get_default_data_dir

__all__ = ["TokenManager", "get_default_data_dir", "get_token_manager"]

logger = logging.getLogger(__name__)


class TokenManager:
    """Manage JWT policy while ``TokenStore`` owns durable state."""

    def __init__(self, secret_key: str | None = None, data_dir: Path | None = None) -> None:
        self.store = TokenStore(data_dir)
        self.data_dir = self.store.data_dir
        self.secret_key = secret_key or self.store.get_or_create_secret()
        self.tokens_file = self.store.tokens_file
        self.used_tokens_file = self.store.used_tokens_file
        self._file_lock = threading.RLock()
        self._last_save_time = 0.0

        self.active_tokens = self._load_tokens()
        self.used_tokens = self._load_used_tokens()
        self._synchronize_used_tokens()
        self._cleanup_expired_tokens()
        logger.info("TokenManager initialized with %s active tokens", len(self.active_tokens))

    def _load_tokens(self) -> dict[str, dict[str, Any]]:
        try:
            return self.store.load_tokens()
        except TokenStoreError as error:
            logger.error("Token state rejected: %s", error)
            return {}

    def _load_used_tokens(self) -> set[str]:
        try:
            return self.store.load_used_tokens()
        except TokenStoreError as error:
            logger.error("Used-token state rejected: %s", error)
            return set()

    def _synchronize_used_tokens(self) -> None:
        changed = False
        for token_id in self.used_tokens:
            token = self.active_tokens.get(token_id)
            if token and token.get("one_time_use") and not token.get("used"):
                token["used"] = True
                changed = True
        self._cleanup_used_tokens()
        if changed:
            self._save_tokens()

    def _save_tokens(self) -> None:
        with self._file_lock:
            self.store.save_tokens(self.active_tokens)
            self._last_save_time = time.monotonic()

    def _save_tokens_throttled(self) -> None:
        if time.monotonic() - self._last_save_time > 60:
            self._save_tokens()

    def _save_used_tokens(self) -> None:
        with self._file_lock:
            self.store.save_used_tokens(self.used_tokens)

    def _cleanup_used_tokens(self) -> None:
        keep = {
            token_id
            for token_id, token in self.active_tokens.items()
            if token.get("one_time_use") and token_id in self.used_tokens
        }
        if keep == self.used_tokens:
            return
        removed = len(self.used_tokens - keep)
        self.used_tokens = keep
        self._save_used_tokens()
        logger.info("Pruned %s stale used token record(s)", removed)

    def _cleanup_expired_tokens(self) -> None:
        now = datetime.now(UTC)
        expired = []
        with self._file_lock:
            for token_id, token in self.active_tokens.items():
                try:
                    expires = datetime.fromisoformat(str(token.get("expires")))
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=UTC)
                    if now > expires:
                        expired.append(token_id)
                except (TypeError, ValueError):
                    expired.append(token_id)

            for token_id in expired:
                self.active_tokens.pop(token_id, None)
                self.used_tokens.discard(token_id)

            if expired:
                try:
                    self._save_tokens()
                    self._save_used_tokens()
                except TokenStoreError as error:
                    logger.error("Unable to persist expired-token cleanup: %s", error)

    def generate_token(self, client_name: str, expiration_days: int = 90, one_time_use: bool = False) -> dict[str, Any]:
        """Generate and durably register a client JWT."""
        token_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        expires = now + timedelta(days=expiration_days)
        payload = {
            "token_id": token_id,
            "client_name": client_name,
            "exp": expires,
            "iat": now,
            "one_time_use": one_time_use,
            "encryption_enabled": True,
        }
        encoded = jwt.encode(payload, self.secret_key, algorithm="HS256")
        token_info = {
            "token_id": token_id,
            "client_name": client_name,
            "expires": expires.isoformat(),
            "created_at": now.isoformat(),
            "one_time_use": one_time_use,
            "used": False,
            "last_seen": None,
            "active": False,
        }

        with self._file_lock:
            self.active_tokens[token_id] = token_info
            try:
                self._save_tokens()
            except TokenStoreError as error:
                self.active_tokens.pop(token_id, None)
                raise ValueError(f"Token generation failed: {error}") from error

        logger.info("Generated token for client %r (ID: %s, one-time: %s)", client_name, token_id, one_time_use)
        return {
            "token": encoded,
            "token_id": token_id,
            "client_name": client_name,
            "expires": expires.isoformat(),
            "one_time_use": one_time_use,
        }

    def validate_token(self, token: str, mark_as_used: bool = True) -> dict[str, Any] | None:
        """Validate a JWT and optionally consume a one-time token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as error:
            logger.warning("Invalid token: %s", error)
            return None

        token_id = payload.get("token_id")
        if not token_id:
            logger.warning("Token missing token_id")
            return None

        with self._file_lock:
            token_info = self.active_tokens.get(token_id)
            if token_info is None:
                logger.warning("Token %s not found in active tokens", token_id)
                return None

            one_time = bool(token_info.get("one_time_use"))
            if one_time and token_id in self.used_tokens:
                logger.warning("One-time token %s already used", token_id)
                return None
            if one_time and not mark_as_used:
                return payload

            token_info["last_seen"] = datetime.now(UTC).isoformat()
            token_info["active"] = True
            if one_time:
                token_info["used"] = True
                self.used_tokens.add(token_id)
                try:
                    self._save_used_tokens()
                    self._save_tokens()
                except TokenStoreError as error:
                    logger.error("Unable to persist one-time token use: %s", error)
                    return None
            else:
                try:
                    self._save_tokens_throttled()
                except TokenStoreError as error:
                    logger.error("Unable to persist token activity: %s", error)

        return payload

    def revoke_token(self, token_id: str) -> bool:
        """Revoke a token and persist the revocation before returning."""
        with self._file_lock:
            token_info = self.active_tokens.pop(token_id, None)
            if token_info is None:
                logger.warning("Token %s not found for revocation", token_id)
                return False
            was_used = token_id in self.used_tokens
            self.used_tokens.discard(token_id)
            try:
                self._save_tokens()
            except TokenStoreError as error:
                self.active_tokens[token_id] = token_info
                if was_used:
                    self.used_tokens.add(token_id)
                logger.error("Failed to revoke token %s: %s", token_id, error)
                return False
            try:
                self._save_used_tokens()
            except TokenStoreError as error:
                logger.warning("Revocation succeeded but stale replay state could not be pruned: %s", error)

        logger.info("Revoked token for client %r (ID: %s)", token_info.get("client_name", "unknown"), token_id)
        return True

    def mark_client_active(self, token_id: str) -> None:
        with self._file_lock:
            if token_id in self.active_tokens:
                self.active_tokens[token_id]["active"] = True
                self.active_tokens[token_id]["last_seen"] = datetime.now(UTC).isoformat()

    def mark_client_inactive(self, token_id: str) -> None:
        with self._file_lock:
            if token_id in self.active_tokens:
                self.active_tokens[token_id]["active"] = False

    def get_active_clients(self) -> list[dict[str, Any]]:
        self._cleanup_expired_tokens()
        with self._file_lock:
            return [
                {
                    "token_id": token_id,
                    "name": token.get("client_name", "Unknown"),
                    "expires": token.get("expires"),
                    "last_seen": token.get("last_seen"),
                    "active": token.get("active", False),
                    "one_time_use": token.get("one_time_use", False),
                    "used": token.get("used", False),
                }
                for token_id, token in self.active_tokens.items()
                if not (token.get("one_time_use") and token.get("used"))
            ]

    def get_server_stats(self) -> dict[str, Any]:
        self._cleanup_expired_tokens()
        with self._file_lock:
            available = sum(
                not (token.get("one_time_use") and token.get("used")) for token in self.active_tokens.values()
            )
            connected = sum(bool(token.get("active")) for token in self.active_tokens.values())
            return {
                "total_tokens": len(self.active_tokens),
                "active_tokens": available,
                "connected_clients": connected,
                "used_one_time_tokens": len(self.used_tokens),
            }

    def close(self) -> None:
        """Compatibility hook; writes are synchronous and already durable."""


_token_manager: TokenManager | None = None


def get_token_manager() -> TokenManager:
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager
