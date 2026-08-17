"""TLS certificate issuance and expiry classification.

Only the self-signed path is implemented (see ``app.tls.engine``'s own
module docstring for why CA import / CSR / ACME renewal are declared
seams). The private key is returned to the caller exactly once, at
issuance time -- this service's own database never stores it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.models.enums import TlsCertificateStatus
from app.models.secrets_tls import TlsCertificate
from app.repositories.secrets_tls import TlsCertificateRepository
from app.tls.engine import classify_certificate_status, generate_self_signed_certificate


@dataclass(frozen=True, slots=True)
class IssuedCertificate:
    record: TlsCertificate
    private_key_pem: str


class TlsCertificateService:
    def __init__(self, repo: TlsCertificateRepository) -> None:
        self._repo = repo

    async def issue_self_signed(
        self, organization_id: UUID, *, common_name: str, valid_days: int = 365
    ) -> IssuedCertificate:
        generated = generate_self_signed_certificate(common_name=common_name, valid_days=valid_days)
        record = await self._repo.create(
            TlsCertificate(
                organization_id=organization_id,
                common_name=common_name,
                issuer=common_name,
                serial_number=generated.serial_number,
                certificate_pem=generated.certificate_pem,
                is_self_signed=True,
                not_before=generated.not_before,
                not_after=generated.not_after,
            )
        )
        return IssuedCertificate(record=record, private_key_pem=generated.private_key_pem)

    async def refresh_status(
        self, certificate: TlsCertificate, *, now: datetime, warning_days: int
    ) -> TlsCertificate:
        status = classify_certificate_status(
            not_after=certificate.not_after, now=now, warning_days=warning_days
        )
        if TlsCertificateStatus(certificate.status) == status:
            return certificate
        certificate.status = status
        return await self._repo.update(certificate)


__all__ = ["IssuedCertificate", "TlsCertificateService"]
