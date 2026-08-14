"""Firmware/version catalog management: the reference data OTA update
planning validates against."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.enums import EdgeDeviceType
from app.models.operations import EdgeFirmware
from app.repositories.operations import EdgeFirmwareRepository


class FirmwareService:
    def __init__(self, repo: EdgeFirmwareRepository) -> None:
        self._repo = repo

    async def register_version(
        self,
        organization_id: UUID,
        *,
        device_type: EdgeDeviceType,
        version_label: str,
        skew_rank: int,
        release_date: datetime | None,
        end_of_life_at: datetime | None,
    ) -> EdgeFirmware:
        return await self._repo.create(
            EdgeFirmware(
                organization_id=organization_id,
                device_type=device_type,
                version_label=version_label,
                skew_rank=skew_rank,
                release_date=release_date,
                end_of_life_at=end_of_life_at,
            )
        )

    async def deprecate(self, firmware: EdgeFirmware) -> EdgeFirmware:
        firmware.is_deprecated = True
        return await self._repo.update(firmware)


__all__ = ["FirmwareService"]
