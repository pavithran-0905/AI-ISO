"""Release build orchestration.

**Event-free.** docs/080 names no build-specific domain event (only
release-lifecycle events: Created/Validated/Signed/Published/
Promoted/Downloaded/Archived plus LTS/EOL), so this service only
tracks status transitions and notifies Release Failure directly on a
failed terminal state -- the same event-free shared-job-engine-with-
direct-notification shape ``services/testing-quality-framework``'s
own ``PipelineService`` uses (Prompt 077).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.models.builds import ReleaseBuild
from app.models.enums import BuildStatus
from app.release_build.engine import TransitionResult, validate_transition
from app.repositories.builds import ReleaseBuildRepository
from app.services.notifications import ReleaseNotifier


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class ReleaseBuildService:
    def __init__(
        self, repo: ReleaseBuildRepository, *, notifier: ReleaseNotifier | None = None
    ) -> None:
        self._repo = repo
        self._notifier = notifier

    async def create(
        self,
        organization_id: UUID,
        *,
        release_version_id: UUID,
        source_commit: str = "",
        builder_identity: str = "",
    ) -> ReleaseBuild:
        return await self._repo.create(
            ReleaseBuild(
                organization_id=organization_id,
                release_version_id=release_version_id,
                source_commit=source_commit,
                builder_identity=builder_identity,
            )
        )

    async def start(self, build: ReleaseBuild, *, now: datetime) -> ReleaseBuild:
        result = validate_transition(build.status, BuildStatus.RUNNING)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        build.status = BuildStatus.RUNNING
        build.started_at = now
        return await self._repo.update(build)

    async def complete(
        self,
        build: ReleaseBuild,
        *,
        status: BuildStatus,
        now: datetime,
        error_message: str = "",
        version_label: str = "",
    ) -> ReleaseBuild:
        result = validate_transition(build.status, status)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        build.status = status
        build.completed_at = now
        build.error_message = error_message
        build = await self._repo.update(build)
        if self._notifier is not None and BuildStatus(status) == BuildStatus.FAILED:
            await self._notifier.notify_release_failure(
                version_label=version_label, error_message=error_message
            )
        return build


__all__ = ["ReleaseBuildService", "TransitionRefusedError"]
