#!/usr/bin/env python3
"""
Generate self-signed SSL certificates for development HTTPS testing
"""

import os
from datetime import datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def generate_self_signed_cert():
    """Generate a self-signed certificate for localhost development"""

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Create certificate
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BG"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Sofia"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Sofia"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "HelpChain Dev"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow())
        .not_valid_after(datetime.utcnow() + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.DNSName("127.0.0.1"),
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Write certificate and key to files
    cert_path = os.path.join(os.path.dirname(__file__), "cert.pem")
    key_path = os.path.join(os.path.dirname(__file__), "key.pem")

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    print(f"Certificate generated: {cert_path}")
    print(f"Private key generated: {key_path}")
    print("\nTo use HTTPS in development:")
    print("1. Set use_https = True in appy.py")
    print("2. Uncomment the context.load_cert_chain lines")
    print(
        "3. Access https://localhost:8000 (you'll need to accept the security warning)"
    )


if __name__ == "__main__":
    try:
        generate_self_signed_cert()
    except ImportError:
        print(
            "cryptography library not installed. Install with: pip install cryptography"
        )
    except Exception as e:
        print(f"Error generating certificate: {e}")
