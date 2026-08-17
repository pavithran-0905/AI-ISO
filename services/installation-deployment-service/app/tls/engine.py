"""Self-signed certificate generation and expiry classification.

Certificate Signing Requests, CA import, and automatic renewal via an
external ACME-style authority are declared seams (docs/075 supports
them conceptually; this build only implements the self-signed path a
fully air-gapped installation can always fall back to, with no
external CA reachable).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.models.enums import TlsCertificateStatus


@dataclass(frozen=True, slots=True)
class GeneratedCertificate:
    certificate_pem: str
    private_key_pem: str
    serial_number: str
    not_before: datetime
    not_after: datetime


def generate_self_signed_certificate(
    *, common_name: str, valid_days: int = 365
) -> GeneratedCertificate:
    """Generate a self-signed RSA certificate for *common_name*, valid
    for *valid_days* starting now."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    not_before = datetime.now(UTC)
    not_after = not_before + timedelta(days=valid_days)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .sign(private_key, hashes.SHA256())
    )
    return GeneratedCertificate(
        certificate_pem=certificate.public_bytes(serialization.Encoding.PEM).decode("ascii"),
        private_key_pem=private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii"),
        serial_number=str(certificate.serial_number),
        not_before=not_before,
        not_after=not_after,
    )


def classify_certificate_status(
    *, not_after: datetime, now: datetime, warning_days: int
) -> TlsCertificateStatus:
    """Classify a certificate as ``EXPIRED`` (past its own
    ``not_after``), ``EXPIRING`` (within *warning_days* of it), or
    ``VALID``."""
    if now >= not_after:
        return TlsCertificateStatus.EXPIRED
    if now >= not_after - timedelta(days=warning_days):
        return TlsCertificateStatus.EXPIRING
    return TlsCertificateStatus.VALID


__all__ = [
    "GeneratedCertificate",
    "classify_certificate_status",
    "generate_self_signed_certificate",
]
