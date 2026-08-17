"""TLS/PKI certificates and generated secrets.

**Never stores a raw secret value or a private key.** ``GeneratedSecret``
stores only ``masked_value`` (via ``shared_core.security.secrets
.mask_secret``); the certificate ``TlsCertificate`` stores is the
public certificate material itself (certificates are, by design, not
sensitive) but never the private key that pairs with it -- matching
this codebase's existing convention of committing only public JWT
verification keys, never private ones.
"""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import SecretStatus, SecretType, TlsCertificateStatus


class TlsCertificate(BaseModel):
    """``tls_certificates`` -- one certificate known to this
    installation -- see ``app.tls.engine`` for expiry classification."""

    __tablename__ = "tls_certificates"

    common_name: Mapped[str] = mapped_column(String(256), index=True)
    issuer: Mapped[str] = mapped_column(String(256), default="")
    serial_number: Mapped[str] = mapped_column(String(64), default="")
    certificate_pem: Mapped[str] = mapped_column(Text, default="")
    is_self_signed: Mapped[bool] = mapped_column(Boolean, default=True)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    not_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[TlsCertificateStatus] = mapped_column(
        String(16), default=TlsCertificateStatus.VALID, index=True
    )


class GeneratedSecret(BaseModel):
    """``generated_secrets`` -- one credential/certificate/key this
    installation generated for itself. The raw value is never
    persisted -- only a masked display form."""

    __tablename__ = "generated_secrets"

    secret_name: Mapped[str] = mapped_column(String(128), index=True)
    secret_type: Mapped[SecretType] = mapped_column(String(16), index=True)
    masked_value: Mapped[str] = mapped_column(String(64))
    status: Mapped[SecretStatus] = mapped_column(
        String(16), default=SecretStatus.ACTIVE, index=True
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["GeneratedSecret", "TlsCertificate"]
