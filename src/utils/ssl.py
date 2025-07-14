"""SSL utility functions for STT Hotkeys."""

import ssl
from pathlib import Path
from typing import Optional, Literal
from ..core.config import get_config, setup_logging

# Get config and logger
config = get_config()
logger = setup_logging(__name__, log_filename="security.txt")

# Type alias for SSL modes
SSLMode = Literal["client", "server"]


def create_ssl_context(mode: SSLMode = "client", auto_generate: bool = True) -> Optional[ssl.SSLContext]:
    """Create SSL context for secure connections.

    This centralizes SSL context creation for both client and server,
    eliminating code duplication.

    Args:
        mode: Either "client" or "server"
        auto_generate: Whether to auto-generate certificates if missing (server only)

    Returns:
        Configured SSL context or None if SSL setup fails

    """
    try:
        # Create appropriate SSL context
        if mode == "server":
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        else:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        # Server-specific certificate loading
        if mode == "server":
            cert_file = config.ssl_cert_file
            key_file = config.ssl_key_file

            # Auto-generate certificates if enabled and files don't exist
            if auto_generate and config.ssl_auto_generate_certs:
                if not (Path(cert_file).exists() and Path(key_file).exists()):
                    logger.info("SSL certificates not found, auto-generating...")
                    _auto_generate_certificates()

            # Load certificate and key
            ssl_context.load_cert_chain(cert_file, key_file)

        # Configure SSL settings based on verify mode
        verify_mode = config.ssl_verify_mode.lower()

        # Detect if we're in production mode (server only)
        if mode == "server":
            is_production = not config.ssl_auto_generate_certs or config.websocket_bind_host not in [
                "localhost",
                "127.0.0.1",
                "::1",
            ]

            # In production, upgrade "none" to "optional" for security
            if is_production and verify_mode == "none":
                logger.warning(
                    "SSL verify_mode 'none' detected in production environment. "
                    "Upgrading to 'optional' for security. Set to 'required' for maximum security."
                )
                verify_mode = "optional"

        # Apply verification settings
        if verify_mode == "none":
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        elif verify_mode == "optional":
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_OPTIONAL
        else:  # required
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED

        logger.info(f"SSL {mode} context configured successfully (verify_mode: {verify_mode})")
        return ssl_context

    except Exception as e:
        logger.exception(f"Failed to setup SSL context for {mode}: {e}")
        return None


def _auto_generate_certificates():
    """Auto-generate self-signed certificates for development."""
    try:
        # Import here to avoid circular dependency
        from scripts.generate_ssl_certs import main as generate_certs

        # Create SSL directory if it doesn't exist
        ssl_dir = Path(config.ssl_cert_file).parent
        ssl_dir.mkdir(parents=True, exist_ok=True)

        # Generate certificates
        generate_certs()
        logger.info("Self-signed certificates generated successfully")

    except ImportError:
        logger.error("Certificate generation script not found. Please run scripts/generate_ssl_certs.py manually")
        raise
    except Exception as e:
        logger.error(f"Failed to auto-generate certificates: {e}")
        raise
