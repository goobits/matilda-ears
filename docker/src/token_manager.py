"""JWT Token Management System for STT Docker Server
Handles token generation, validation, and one-time use enforcement
"""

import base64
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any, Set
import uuid

import jwt

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages JWT tokens for client authentication"""

    def __init__(self, secret_key: Optional[str] = None, data_dir: Path = None):
        self.data_dir = data_dir or Path("/app/data")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.secret_key = secret_key or self._get_or_create_secret()
        self.tokens_file = self.data_dir / "tokens.json"
        self.used_tokens_file = self.data_dir / "used_tokens.json"

        # In-memory token storage
        self.active_tokens: Dict[str, Dict[str, Any]] = {}
        self.used_tokens: Set[str] = set()

        # Load existing tokens
        self._load_tokens()
        self._load_used_tokens()

        logger.info(f"TokenManager initialized with {len(self.active_tokens)} active tokens")

    def _get_or_create_secret(self) -> str:
        """Get or create JWT secret key"""
        secret_file = self.data_dir / "jwt_secret.key"

        if secret_file.exists():
            return secret_file.read_text().strip()
        # Generate new secret
        secret = base64.urlsafe_b64encode(os.urandom(32)).decode()
        secret_file.write_text(secret)
        os.chmod(secret_file, 0o600)
        logger.info("Generated new JWT secret key")
        return secret

    def _load_tokens(self):
        """Load active tokens from storage"""
        try:
            if self.tokens_file.exists():
                data = json.loads(self.tokens_file.read_text())
                self.active_tokens = data

                # Clean expired tokens
                self._cleanup_expired_tokens()

        except Exception as e:
            logger.error(f"Failed to load tokens: {e}")
            self.active_tokens = {}

    def _load_used_tokens(self):
        """Load used tokens from storage"""
        try:
            if self.used_tokens_file.exists():
                data = json.loads(self.used_tokens_file.read_text())
                self.used_tokens = set(data.get("used_tokens", []))

        except Exception as e:
            logger.error(f"Failed to load used tokens: {e}")
            self.used_tokens = set()

    def _save_tokens(self):
        """Save active tokens to storage"""
        try:
            self.tokens_file.write_text(json.dumps(self.active_tokens, indent=2))
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")

    def _save_used_tokens(self):
        """Save used tokens to storage"""
        try:
            data = {"used_tokens": list(self.used_tokens)}
            self.used_tokens_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save used tokens: {e}")

    def _cleanup_expired_tokens(self):
        """Remove expired tokens from active tokens"""
        now = datetime.utcnow()
        expired_tokens = []

        for token_id, token_info in self.active_tokens.items():
            try:
                expires_str = token_info.get("expires")
                if expires_str:
                    expires = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                    if now > expires:
                        expired_tokens.append(token_id)
            except Exception as e:
                logger.warning(f"Error checking expiration for token {token_id}: {e}")
                expired_tokens.append(token_id)

        for token_id in expired_tokens:
            del self.active_tokens[token_id]
            logger.info(f"Removed expired token: {token_id}")

        if expired_tokens:
            self._save_tokens()

    def generate_token(self, client_name: str, expiration_days: int = 90, one_time_use: bool = False) -> Dict[str, Any]:
        """Generate a new JWT token for a client

        Args:
            client_name: Name of the client
            expiration_days: Number of days until token expires
            one_time_use: Whether token can only be used once

        Returns:
            Dictionary with token information

        """
        try:
            token_id = str(uuid.uuid4())
            expires = datetime.utcnow() + timedelta(days=expiration_days)

            # Create JWT payload
            payload = {
                "token_id": token_id,
                "client_name": client_name,
                "exp": expires,
                "iat": datetime.utcnow(),
                "one_time_use": one_time_use,
                "encryption_enabled": True,
            }

            # Generate JWT token
            token = jwt.encode(payload, self.secret_key, algorithm="HS256")

            # Store token info
            token_info = {
                "token_id": token_id,
                "client_name": client_name,
                "expires": expires.isoformat(),
                "created_at": datetime.utcnow().isoformat(),
                "one_time_use": one_time_use,
                "used": False,
                "last_seen": None,
                "active": False,
            }

            self.active_tokens[token_id] = token_info
            self._save_tokens()

            logger.info(f"Generated token for client '{client_name}' (ID: {token_id}, one-time: {one_time_use})")

            return {
                "token": token,
                "token_id": token_id,
                "client_name": client_name,
                "expires": expires.isoformat(),
                "one_time_use": one_time_use,
            }

        except Exception as e:
            logger.error(f"Failed to generate token: {e}")
            raise ValueError(f"Token generation failed: {e}")

    def validate_token(self, token: str, mark_as_used: bool = False) -> Optional[Dict[str, Any]]:
        """Validate a JWT token

        Args:
            token: JWT token to validate
            mark_as_used: Whether to mark one-time tokens as used

        Returns:
            Token payload if valid, None otherwise

        """
        try:
            # Decode JWT token
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            token_id = payload.get("token_id")

            if not token_id:
                logger.warning("Token missing token_id")
                return None

            # Check if token exists in active tokens
            if token_id not in self.active_tokens:
                logger.warning(f"Token {token_id} not found in active tokens")
                return None

            token_info = self.active_tokens[token_id]

            # Check if token was already used (for one-time tokens)
            if token_info.get("one_time_use", False):
                if token_id in self.used_tokens:
                    logger.warning(f"One-time token {token_id} already used")
                    return None

                if mark_as_used:
                    # Mark as used
                    self.used_tokens.add(token_id)
                    self.active_tokens[token_id]["used"] = True
                    self._save_used_tokens()
                    self._save_tokens()
                    logger.info(f"Marked one-time token {token_id} as used")

            # Update last seen
            self.active_tokens[token_id]["last_seen"] = datetime.utcnow().isoformat()
            self.active_tokens[token_id]["active"] = True
            self._save_tokens()

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None

    def revoke_token(self, token_id: str) -> bool:
        """Revoke a token by removing it from active tokens

        Args:
            token_id: ID of token to revoke

        Returns:
            True if token was revoked, False if not found

        """
        try:
            if token_id in self.active_tokens:
                client_name = self.active_tokens[token_id].get("client_name", "unknown")
                del self.active_tokens[token_id]
                self._save_tokens()

                logger.info(f"Revoked token for client '{client_name}' (ID: {token_id})")
                return True
            logger.warning(f"Token {token_id} not found for revocation")
            return False

        except Exception as e:
            logger.error(f"Failed to revoke token {token_id}: {e}")
            return False

    def mark_client_active(self, token_id: str):
        """Mark a client as active"""
        if token_id in self.active_tokens:
            self.active_tokens[token_id]["active"] = True
            self.active_tokens[token_id]["last_seen"] = datetime.utcnow().isoformat()

    def mark_client_inactive(self, token_id: str):
        """Mark a client as inactive"""
        if token_id in self.active_tokens:
            self.active_tokens[token_id]["active"] = False

    def get_active_clients(self) -> list:
        """Get list of all clients with active tokens"""
        self._cleanup_expired_tokens()

        clients = []
        for token_id, token_info in self.active_tokens.items():
            # Skip used one-time tokens
            if token_info.get("one_time_use", False) and token_info.get("used", False):
                continue

            clients.append(
                {
                    "token_id": token_id,
                    "name": token_info.get("client_name", "Unknown"),
                    "expires": token_info.get("expires"),
                    "last_seen": token_info.get("last_seen"),
                    "active": token_info.get("active", False),
                    "one_time_use": token_info.get("one_time_use", False),
                    "used": token_info.get("used", False),
                }
            )

        return clients

    def get_server_stats(self) -> Dict[str, Any]:
        """Get token manager statistics"""
        self._cleanup_expired_tokens()

        active_count = len(
            [t for t in self.active_tokens.values() if not (t.get("one_time_use", False) and t.get("used", False))]
        )
        connected_count = len([t for t in self.active_tokens.values() if t.get("active", False)])

        return {
            "total_tokens": len(self.active_tokens),
            "active_tokens": active_count,
            "connected_clients": connected_count,
            "used_one_time_tokens": len(self.used_tokens),
        }


# Global token manager instance
_token_manager = None


def get_token_manager() -> TokenManager:
    """Get the global token manager instance"""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager
