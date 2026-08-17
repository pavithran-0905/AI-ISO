"""Release note recording."""

from __future__ import annotations

from uuid import UUID

from app.models.enums import ReleaseNoteType
from app.models.notes import ReleaseNote
from app.repositories.notes import ReleaseNoteRepository


class ReleaseNoteService:
    def __init__(self, repo: ReleaseNoteRepository) -> None:
        self._repo = repo

    async def record(
        self,
        organization_id: UUID,
        *,
        release_version_id: UUID,
        note_type: ReleaseNoteType,
        summary: str,
        detail: str = "",
    ) -> ReleaseNote:
        return await self._repo.create(
            ReleaseNote(
                organization_id=organization_id,
                release_version_id=release_version_id,
                note_type=note_type,
                summary=summary,
                detail=detail,
            )
        )


__all__ = ["ReleaseNoteService"]
