"""End-to-End Encryption Module for STT Docker Server
Implements RSA + AES hybrid encryption for client-server communication
"""

import base64
import json
import logging
import os
from typing import Dict, Optional, Any
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pathlib import Path

logger = logging.getLogger(__name__)


class EncryptionManager:
    """Manages RSA key pairs and hybrid encryption for the STT server"""

    def __init__(self, keys_dir: Path = None):
        self.keys_dir = keys_dir or Path("/app/data/encryption")
        self.keys_dir.mkdir(parents=True, exist_ok=True)

        self.private_key = None
        self.public_key = None
        self.public_key_pem = None

        self._load_or_generate_keys()

    def _load_or_generate_keys(self):
        """Load existing RSA keys or generate new ones"""
        private_key_path = self.keys_dir / "server_private.pem"
        public_key_path = self.keys_dir / "server_public.pem"

        try:
            if private_key_path.exists() and public_key_path.exists():
                # Load existing keys
                with open(private_key_path, "rb") as f:
                    self.private_key = serialization.load_pem_private_key(f.read(), password=None)

                with open(public_key_path, "rb") as f:
                    self.public_key_pem = f.read()
                    self.public_key = serialization.load_pem_public_key(self.public_key_pem)

                logger.info("Loaded existing RSA key pair for encryption")
            else:
                # Generate new keys
                self._generate_key_pair()
                logger.info("Generated new RSA key pair for encryption")

        except Exception as e:
            logger.error(f"Failed to load encryption keys: {e}")
            self._generate_key_pair()

    def _generate_key_pair(self):
        """Generate a new RSA key pair"""
        try:
            # Generate private key
            self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

            # Get public key
            self.public_key = self.private_key.public_key()

            # Serialize keys
            private_pem = self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )

            self.public_key_pem = self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            # Save keys to disk
            private_key_path = self.keys_dir / "server_private.pem"
            public_key_path = self.keys_dir / "server_public.pem"

            with open(private_key_path, "wb") as f:
                f.write(private_pem)

            with open(public_key_path, "wb") as f:
                f.write(self.public_key_pem)

            # Set secure permissions
            os.chmod(private_key_path, 0o600)
            os.chmod(public_key_path, 0o644)

        except Exception as e:
            logger.error(f"Failed to generate RSA key pair: {e}")
            raise

    def get_public_key_pem(self) -> str:
        """Get the server's public key in PEM format for clients"""
        return self.public_key_pem.decode("utf-8")

    def decrypt_message(self, encrypted_data: Dict[str, Any]) -> str:
        """Decrypt a message using hybrid RSA+AES decryption

        Args:
            encrypted_data: Dictionary containing:
                - encrypted_aes_key: RSA-encrypted AES key (base64)
                - encrypted_content: AES-encrypted content (base64)
                - iv: AES initialization vector (base64)

        Returns:
            Decrypted plaintext string

        """
        try:
            # Extract components
            encrypted_aes_key_b64 = encrypted_data.get("encrypted_aes_key")
            encrypted_content_b64 = encrypted_data.get("encrypted_content")
            iv_b64 = encrypted_data.get("iv")

            if not all([encrypted_aes_key_b64, encrypted_content_b64, iv_b64]):
                raise ValueError("Missing encryption components")

            # Decode base64
            encrypted_aes_key = base64.b64decode(encrypted_aes_key_b64)
            encrypted_content = base64.b64decode(encrypted_content_b64)
            iv = base64.b64decode(iv_b64)

            # Decrypt AES key with RSA private key
            aes_key = self.private_key.decrypt(
                encrypted_aes_key,
                padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
            )

            # Decrypt content with AES key
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            padded_plaintext = decryptor.update(encrypted_content) + decryptor.finalize()

            # Remove PKCS7 padding
            padding_length = padded_plaintext[-1]
            plaintext = padded_plaintext[:-padding_length]

            return plaintext.decode("utf-8")

        except Exception as e:
            logger.error(f"Failed to decrypt message: {e}")
            raise ValueError(f"Decryption failed: {e}")

    def encrypt_response(self, plaintext: str, client_public_key_pem: str) -> Dict[str, str]:
        """Encrypt a response message for the client using their public key

        Args:
            plaintext: Message to encrypt
            client_public_key_pem: Client's public key in PEM format

        Returns:
            Dictionary with encrypted components

        """
        try:
            # Load client's public key
            client_public_key = serialization.load_pem_public_key(client_public_key_pem.encode("utf-8"))

            # Generate AES key and IV
            aes_key = os.urandom(32)  # 256-bit key
            iv = os.urandom(16)  # 128-bit IV

            # Pad plaintext for AES (PKCS7 padding)
            plaintext_bytes = plaintext.encode("utf-8")
            padding_length = 16 - (len(plaintext_bytes) % 16)
            padded_plaintext = plaintext_bytes + bytes([padding_length] * padding_length)

            # Encrypt content with AES
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
            encryptor = cipher.encryptor()
            encrypted_content = encryptor.update(padded_plaintext) + encryptor.finalize()

            # Encrypt AES key with client's RSA public key
            encrypted_aes_key = client_public_key.encrypt(
                aes_key,
                padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
            )

            # Return base64-encoded components
            return {
                "encrypted_aes_key": base64.b64encode(encrypted_aes_key).decode("utf-8"),
                "encrypted_content": base64.b64encode(encrypted_content).decode("utf-8"),
                "iv": base64.b64encode(iv).decode("utf-8"),
            }

        except Exception as e:
            logger.error(f"Failed to encrypt response: {e}")
            raise ValueError(f"Encryption failed: {e}")


class EncryptionWebSocketHandler:
    """WebSocket message handler with end-to-end encryption support"""

    def __init__(self, encryption_manager: EncryptionManager):
        self.encryption = encryption_manager
        self.client_public_keys: Dict[str, str] = {}  # client_id -> public_key_pem

    def handle_key_exchange(self, client_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle client public key exchange

        Args:
            client_id: Unique client identifier
            message: Message containing client's public key

        Returns:
            Response with server's public key

        """
        try:
            client_public_key_pem = message.get("public_key")
            if not client_public_key_pem:
                raise ValueError("No public key provided")

            # Store client's public key
            self.client_public_keys[client_id] = client_public_key_pem

            logger.info(f"Stored public key for client {client_id}")

            # Return server's public key
            return {
                "type": "key_exchange_response",
                "public_key": self.encryption.get_public_key_pem(),
                "encryption_enabled": True,
            }

        except Exception as e:
            logger.error(f"Key exchange failed for client {client_id}: {e}")
            return {"type": "error", "message": f"Key exchange failed: {e}"}

    def decrypt_client_message(self, client_id: str, encrypted_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Decrypt a message from a client

        Args:
            client_id: Client identifier
            encrypted_message: Encrypted message data

        Returns:
            Decrypted message dictionary or None if decryption fails

        """
        try:
            # Check if this is an encrypted message
            if encrypted_message.get("encrypted") is not True:
                # Not encrypted, return as-is
                return encrypted_message

            # Extract encrypted payload
            encrypted_payload = encrypted_message.get("payload")
            if not encrypted_payload:
                raise ValueError("No encrypted payload found")

            # Decrypt the payload
            decrypted_json = self.encryption.decrypt_message(encrypted_payload)

            # Parse decrypted JSON
            decrypted_message = json.loads(decrypted_json)

            logger.debug(f"Successfully decrypted message from client {client_id}")
            return decrypted_message

        except Exception as e:
            logger.error(f"Failed to decrypt message from client {client_id}: {e}")
            return None

    def encrypt_response(self, client_id: str, response: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt a response for a client

        Args:
            client_id: Client identifier
            response: Response data to encrypt

        Returns:
            Encrypted response or original response if encryption not available

        """
        try:
            # Check if we have the client's public key
            client_public_key = self.client_public_keys.get(client_id)
            if not client_public_key:
                # No encryption key available, send plaintext
                logger.warning(f"No public key for client {client_id}, sending plaintext")
                return response

            # Encrypt the response
            response_json = json.dumps(response)
            encrypted_payload = self.encryption.encrypt_response(response_json, client_public_key)

            return {"encrypted": True, "payload": encrypted_payload}

        except Exception as e:
            logger.error(f"Failed to encrypt response for client {client_id}: {e}")
            # Fall back to plaintext
            return response

    def cleanup_client(self, client_id: str):
        """Clean up client data when they disconnect"""
        if client_id in self.client_public_keys:
            del self.client_public_keys[client_id]
            logger.info(f"Cleaned up encryption data for client {client_id}")


# Global encryption manager instance
_encryption_manager = None


def get_encryption_manager() -> EncryptionManager:
    """Get the global encryption manager instance"""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager
