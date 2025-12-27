#!/usr/bin/env python3
"""Generate self-signed SSL certificates for Matilda WebSocket server development.
This script creates certificates suitable for development and testing purposes.
"""
import os
import sys
import subprocess
import datetime
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matilda_ears.core.config import get_config


def generate_openssl_config(cert_dir: Path, hostname: str = "localhost") -> Path:
    """Generate OpenSSL configuration for certificate generation"""
    config_content = f"""[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = {hostname}
O = STT Hotkey System
L = Development
ST = Development
C = US

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = *.localhost
IP.1 = 127.0.0.1
IP.2 = ::1
"""

    config_file = cert_dir / "openssl.conf"
    with open(config_file, "w") as f:
        f.write(config_content)

    return config_file


def check_openssl_available() -> bool:
    """Check if OpenSSL is available on the system"""
    try:
        result = subprocess.run(["openssl", "version"], capture_output=True, text=True, check=True)
        print(f"✅ OpenSSL available: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ OpenSSL not found. Please install OpenSSL to generate certificates.")
        return False


def generate_certificates_openssl(cert_dir: Path, key_file: Path, cert_file: Path, validity_days: int = 365) -> bool:
    """Generate certificates using OpenSSL command line tool"""
    print("🔐 Generating SSL certificates using OpenSSL...")

    # Generate OpenSSL config
    openssl_config = generate_openssl_config(cert_dir)

    try:
        # Generate private key
        print("   Generating private key...")
        subprocess.run(["openssl", "genrsa", "-out", str(key_file), "2048"], check=True, capture_output=True)

        # Generate certificate
        print("   Generating certificate...")
        subprocess.run(
            [
                "openssl",
                "req",
                "-new",
                "-x509",
                "-key",
                str(key_file),
                "-out",
                str(cert_file),
                "-days",
                str(validity_days),
                "-config",
                str(openssl_config),
            ],
            check=True,
            capture_output=True,
        )

        # Clean up config file
        openssl_config.unlink()

        print("✅ Certificates generated successfully!")
        print(f"   Private key: {key_file}")
        print(f"   Certificate: {cert_file}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate certificates: {e}")
        return False


def generate_certificates_python(cert_dir: Path, key_file: Path, cert_file: Path, validity_days: int = 365) -> bool:
    """Generate certificates using Python cryptography library"""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        import ipaddress

        print("🔐 Generating SSL certificates using Python cryptography...")

        # Generate private key
        print("   Generating private key...")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Create certificate
        print("   Generating certificate...")
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Development"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Development"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "STT Hotkey System"),
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ]
        )

        # Build certificate
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=validity_days))
            .add_extension(
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName("localhost"),
                        x509.DNSName("*.localhost"),
                        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                        x509.IPAddress(ipaddress.IPv6Address("::1")),
                    ]
                ),
                critical=False,
            )
            .add_extension(
                x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
            .sign(private_key, hashes.SHA256())
        )

        # Write private key
        with open(key_file, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Write certificate
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        print("✅ Certificates generated successfully!")
        print(f"   Private key: {key_file}")
        print(f"   Certificate: {cert_file}")
        return True

    except ImportError:
        print("❌ Python cryptography library not available.")
        print("   Install with: pip install cryptography")
        return False
    except Exception as e:
        print(f"❌ Failed to generate certificates: {e}")
        return False


def main() -> None:
    """Main certificate generation function"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate SSL certificates for Matilda WebSocket server")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing certificates without prompting")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    args = parser.parse_args()

    if not args.quiet:
        print("🔒 STT Hotkey System - SSL Certificate Generator")
        print("=" * 50)

    # Load configuration
    try:
        config = get_config()
        cert_file = config.ssl_cert_file
        key_file = config.ssl_key_file
        validity_days = config.ssl_cert_validity_days
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        sys.exit(1)

    # Create certificate directory
    cert_dir = Path(cert_file).parent
    cert_dir.mkdir(parents=True, exist_ok=True)

    # Convert to absolute paths
    cert_path = cert_dir / Path(cert_file).name
    key_path = cert_dir / Path(key_file).name

    # Check if certificates already exist
    if cert_path.exists() and key_path.exists():
        if args.overwrite:
            if not args.quiet:
                print("Certificates exist - overwriting as requested")
        elif sys.stdin.isatty():
            # Interactive terminal - ask user
            response = input("Certificates already exist. Overwrite? (y/N): ")
            if response.lower() != "y":
                print("Cancelled.")
                sys.exit(0)
        # Non-interactive (automated install) - always overwrite
        elif not args.quiet:
            print("Certificates exist - overwriting for fresh install")

    print(f"📁 Certificate directory: {cert_dir}")
    print(f"🔑 Private key file: {key_path}")
    print(f"📜 Certificate file: {cert_path}")
    print(f"⏰ Validity period: {validity_days} days")
    print()

    # Try OpenSSL first (more compatible), then Python cryptography
    success = False

    if check_openssl_available():
        success = generate_certificates_openssl(cert_dir, key_path, cert_path, validity_days)

    if not success:
        print("\nFalling back to Python cryptography library...")
        success = generate_certificates_python(cert_dir, key_path, cert_path, validity_days)

    if success:
        # Set appropriate permissions
        try:
            os.chmod(key_path, 0o600)  # Private key should be readable only by owner
            os.chmod(cert_path, 0o644)  # Certificate can be readable by all
            print("🔒 Set secure permissions on certificate files")
        except Exception as e:
            print(f"⚠️  Warning: Could not set file permissions: {e}")

        print("\n🎉 SSL certificates generated successfully!")
        print("\n📋 Next steps:")
        print("   1. Update config.jsonc to enable SSL: 'server.websocket.ssl.enabled: true'")
        print("   2. Restart the WebSocket server: ./server.py restart-ws")
        print("   3. Clients will connect using wss:// instead of ws://")
        print("\n⚠️  Note: These are self-signed certificates for development only.")
        print("   For production, use certificates from a trusted CA.")

    else:
        print("\n❌ Failed to generate certificates using any method.")
        print("Please install either OpenSSL or Python cryptography library.")
        sys.exit(1)


if __name__ == "__main__":
    main()
