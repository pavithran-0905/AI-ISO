"""The retention sweep worker (docs/063 "DOCUMENT LIFECYCLE").

Archives documents whose retention period has passed, and recovers ones
stuck mid-pipeline. **Leader-elected** through ``shared_core.scheduler``;
see :mod:`app.workers.registrar`.

**Archived, not deleted.** The audit trail references every document, and
hard-deleting one would leave audit rows pointing at nothing -- which is
indistinguishable from an audit trail that was tampered with. Retention
moves a document out of the active corpus and leaves its history intact.

**Stalled documents are requeued, not failed.** A document left in
``PARSING`` because a worker was killed mid-run has nothing wrong with it;
the run was interrupted. Marking it ``FAILED`` would put a deployment
restart into the record as a document defect.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared_core.logging.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.events.document_events import DocumentArchivedEvent
from app.models.enums import DocumentStatus, JobStatus, ProcessingStage
from app.models.operations import DocumentAudit, DocumentProcessingJob
from app.services.bundle import build_repositories
from app.types import EventPublisher

logger = get_logger("app.workers.retention_sweep")

_SOURCE_SERVICE = "document-intelligence-service"

STALLED_STATUSES = (
    DocumentStatus.PARSING,
    DocumentStatus.OCR_PENDING,
    DocumentStatus.CLASSIFYING,
    DocumentStatus.EXTRACTING,
    DocumentStatus.VALIDATING,
    DocumentStatus.SUMMARIZING,
    DocumentStatus.TRANSLATING,
)
"""Statuses a document can only be in while something is actively working
on it. Still in one after the stall window means nothing is."""

RECOVERY_STAGES = (
    ProcessingStage.PARSING,
    ProcessingStage.LAYOUT,
    ProcessingStage.ENTITY_EXTRACTION,
    ProcessingStage.TABLE_EXTRACTION,
    ProcessingStage.FORM_EXTRACTION,
    ProcessingStage.CLASSIFICATION,
    ProcessingStage.VALIDATION_RULES,
)


class RetentionSweepWorker:
    """Archives expired documents and recovers stalled ones."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        publish_event: EventPublisher,
        stall_minutes: int = 30,
        batch_size: int = 100,
    ) -> None:
        self._session_factory = session_factory
        self._publish_event = publish_event
        self._stall_minutes = stall_minutes
        self._batch_size = batch_size

    async def run_job(self, _job: object) -> None:
        """Entry point matching ``shared_core.scheduler``'s own ``JobFn``."""
        await self.tick()

    async def tick(self) -> tuple[int, int]:
        """Archive expired documents and requeue stalled ones.

        Returns the two counts separately: they are different problems
        with different causes, and one number would hide whichever was
        smaller.
        """
        archived = await self._archive_expired()
        recovered = await self._recover_stalled()
        if archived or recovered:
            logger.info(
                "retention sweep completed",
                extra={"extra_fields": {"archived": archived, "recovered": recovered}},
            )
        return archived, recovered

    async def _archive_expired(self) -> int:
        """Archive every document past its expiry date."""
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            repos = build_repositories(session)
            candidates = await repos.documents.list_expired(now, limit=self._batch_size)
            for document in candidates:
                await repos.documents.mark_status(document.id, DocumentStatus.ARCHIVED)
                expiry = (
                    document.expires_at.isoformat() if document.expires_at else "an unrecorded time"
                )
                await repos.audits.create(
                    DocumentAudit(
                        organization_id=document.organization_id,
                        action="archived",
                        entity_type="document",
                        entity_id=document.id,
                        occurred_at=now,
                        actor_id=None,
                        summary=f"Archived automatically; retention expired at {expiry}.",
                    )
                )
                await self._publish_event(
                    DocumentArchivedEvent(
                        source_service=_SOURCE_SERVICE,
                        organization_id=document.organization_id,
                        payload={
                            "document_id": str(document.id),
                            "reason": "retention_expired",
                            "expires_at": (
                                document.expires_at.isoformat() if document.expires_at else None
                            ),
                        },
                    )
                )
            await session.commit()
            return len(candidates)

    async def _recover_stalled(self) -> int:
        """Requeue documents stuck mid-pipeline."""
        cutoff = datetime.now(UTC) - timedelta(minutes=self._stall_minutes)
        async with self._session_factory() as session:
            repos = build_repositories(session)
            stalled = await repos.documents.list_stalled(
                statuses=STALLED_STATUSES, older_than=cutoff, limit=self._batch_size
            )
            for document in stalled:
                await repos.jobs.create(
                    DocumentProcessingJob(
                        organization_id=document.organization_id,
                        document_id=document.id,
                        status=JobStatus.QUEUED,
                        stages=[str(stage) for stage in RECOVERY_STAGES],
                        priority=20,
                        scheduled_at=datetime.now(UTC),
                        requested_by="retention-sweep",
                        job_metadata={"reason": "recovered from a stalled run"},
                    )
                )
                stuck_in = str(document.status)
                await repos.documents.mark_status(document.id, DocumentStatus.UPLOADED)
                await repos.audits.create(
                    DocumentAudit(
                        organization_id=document.organization_id,
                        action="requeued",
                        entity_type="document",
                        entity_id=document.id,
                        occurred_at=datetime.now(UTC),
                        actor_id=None,
                        summary=(
                            f"Requeued after sitting in {stuck_in} for over "
                            f"{self._stall_minutes} minutes."
                        ),
                    )
                )
            await session.commit()
            return len(stalled)


__all__ = ["RECOVERY_STAGES", "STALLED_STATUSES", "RetentionSweepWorker"]
