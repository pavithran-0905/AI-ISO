"""RAG notifications (docs/062 "NOTIFICATIONS", integrating Prompt 025).

The six the spec names: Index Failed, Knowledge Source Unavailable,
Embedding Failure, Reindex Completed, Storage Threshold Reached, and
Evaluation Completed.

A thin wrapper over :class:`shared_core.notifications.manager
.NotificationManager` using the same best-effort ``_send`` pattern every
prior AI-IOS service established -- **a notification failure never blocks
the operation that triggered it**. An indexing job that succeeded but
could not tell anyone still indexed the documents, and rolling it back
because the mail server was down would turn a cosmetic problem into a
real one.
"""

from __future__ import annotations

from shared_core.enums.notification_channel import NotificationChannel
from shared_core.enums.notification_type import NotificationType
from shared_core.exceptions.notification import NotificationError
from shared_core.logging.logger import get_logger
from shared_core.notifications.manager import NotificationManager

logger = get_logger("app.notifications.rag_notifications")


class RagNotificationService:
    """Sends every RAG notification, best-effort."""

    def __init__(self, manager: NotificationManager) -> None:
        self._manager = manager

    async def _send(
        self, *, user_id: str, subject: str, body: str, notification_type: NotificationType
    ) -> None:
        try:
            await self._manager.send(
                user_id=user_id,
                notification_type=notification_type,
                body=body,
                channel=NotificationChannel.EMAIL,
                subject=subject,
            )
        except NotificationError:
            logger.warning(
                "Failed to send a RAG notification.",
                extra={"extra_fields": {"user_id": user_id, "subject": subject}},
            )

    async def send_index_failed(self, user_id: str, *, title: str, reason: str) -> None:
        """Notify that a document could not be indexed.

        Names the document and the reason, because "indexing failed" with
        neither is a notification whose only possible response is to go
        and look -- which the notification was supposed to save.
        """
        await self._send(
            user_id=user_id,
            subject="An AI-IOS document could not be indexed",
            body=f"Indexing failed for '{title}': {reason}",
            notification_type=NotificationType.ERROR,
        )

    async def send_source_unavailable(self, user_id: str, *, source: str, reason: str) -> None:
        """Notify that a knowledge source could not be reached.

        Distinct from an index failure: the documents are fine and the
        *source* is unreachable, which is somebody else's system to fix.
        """
        await self._send(
            user_id=user_id,
            subject="An AI-IOS knowledge source is unavailable",
            body=f"The knowledge source '{source}' could not be reached: {reason}",
            notification_type=NotificationType.WARNING,
        )

    async def send_embedding_failed(self, user_id: str, *, provider: str, reason: str) -> None:
        """Notify that the embedding provider failed.

        Worth its own notification because it halts *all* indexing rather
        than one document, and the remedy is usually a credential or a
        quota rather than anything about the corpus.
        """
        await self._send(
            user_id=user_id,
            subject="AI-IOS embedding generation failed",
            body=f"The embedding provider '{provider}' failed: {reason}",
            notification_type=NotificationType.ERROR,
        )

    async def send_reindex_completed(self, user_id: str, *, succeeded: int, failed: int) -> None:
        """Notify that a reindex finished, with both counts.

        Both numbers, always. "Reindex completed" alone reads as success
        even when half the corpus failed, and the failure count is the
        only part anyone needs to act on.
        """
        await self._send(
            user_id=user_id,
            subject="An AI-IOS reindex has completed",
            body=(f"Reindexing finished: {succeeded} document(s) indexed, " f"{failed} failed."),
            notification_type=(
                NotificationType.WARNING if failed else NotificationType.INFORMATION
            ),
        )

    async def send_storage_threshold(
        self, user_id: str, *, used_bytes: int, threshold_bytes: int
    ) -> None:
        """Notify that the index has grown past its configured threshold."""
        await self._send(
            user_id=user_id,
            subject="AI-IOS knowledge index storage threshold reached",
            body=(
                f"The knowledge index now occupies {used_bytes} bytes, past the "
                f"{threshold_bytes}-byte threshold."
            ),
            notification_type=NotificationType.WARNING,
        )

    async def send_evaluation_completed(
        self, user_id: str, *, queries: int, precision: float | None
    ) -> None:
        """Notify that an evaluation run finished.

        Reports "not measured" rather than a number when no feedback
        existed: printing 0.0 for an unjudged corpus would read as a
        retriever returning nothing useful, which is a different and much
        more alarming fact.
        """
        measured = f"{precision:.2f}" if precision is not None else "not measured"
        await self._send(
            user_id=user_id,
            subject="An AI-IOS retrieval evaluation has completed",
            body=f"Evaluated {queries} judged query/queries. Precision: {measured}.",
            notification_type=NotificationType.INFORMATION,
        )


__all__ = ["RagNotificationService"]
