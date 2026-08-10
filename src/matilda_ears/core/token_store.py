"""Durable storage for JWT signing and token state."""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


class TokenStoreError(RuntimeError):
    """Raised when durable token state cannot be read or written safely."""


def get_default_data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".local" / "share"
    return base / "ears"


class TokenStore:
    """Own atomic filesystem persistence for ``TokenManager``."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or get_default_data_dir()
        self.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            self.data_dir.chmod(0o700)
        except OSError:
            pass

        self.secret_file = self.data_dir / "jwt_secret.key"
        self.tokens_file = self.data_dir / "tokens.json"
        self.used_tokens_file = self.data_dir / "used_tokens.json"

    def get_or_create_secret(self) -> str:
        if self.secret_file.exists():
            secret = self.secret_file.read_text(encoding="utf-8").strip()
            if secret:
                return secret
            raise TokenStoreError(f"JWT secret is empty: {self.secret_file}")

        secret = base64.urlsafe_b64encode(os.urandom(32)).decode()
        try:
            descriptor = os.open(self.secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            existing = self.secret_file.read_text(encoding="utf-8").strip()
            if existing:
                return existing
            raise TokenStoreError(f"JWT secret is empty: {self.secret_file}") from None

        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                file.write(secret)
                file.flush()
                os.fsync(file.fileno())
        except Exception:
            self.secret_file.unlink(missing_ok=True)
            raise
        return secret

    def load_tokens(self) -> dict[str, dict[str, Any]]:
        value = self._read_json(self.tokens_file, {})
        if not isinstance(value, dict) or not all(isinstance(item, dict) for item in value.values()):
            raise TokenStoreError(f"Invalid token state: {self.tokens_file}")
        return value

    def save_tokens(self, tokens: dict[str, dict[str, Any]]) -> None:
        self._write_json(self.tokens_file, tokens)

    def load_used_tokens(self) -> set[str]:
        value = self._read_json(self.used_tokens_file, {"used_tokens": []})
        if not isinstance(value, dict) or not isinstance(value.get("used_tokens"), list):
            raise TokenStoreError(f"Invalid used-token state: {self.used_tokens_file}")
        return {str(token_id) for token_id in value["used_tokens"]}

    def save_used_tokens(self, tokens: set[str]) -> None:
        self._write_json(self.used_tokens_file, {"used_tokens": sorted(tokens)})

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise TokenStoreError(f"Unable to read {path}: {error}") from error

    def _write_json(self, path: Path, value: Any) -> None:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=self.data_dir)
        temporary = Path(temporary_name)
        try:
            os.chmod(temporary, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(value, file, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(path)
        except Exception as error:
            temporary.unlink(missing_ok=True)
            raise TokenStoreError(f"Unable to write {path}: {error}") from error
