"""Document notifications (docs/063 "NOTIFICATIONS", integrating Prompt 025).

The six the spec names: OCR Failed, Validation Failed, Review Assigned,
Review Completed, Processing Completed, and Translation Completed.

A thin wrapper over :class:`shared_core.notifications.manager
.NotificationManager` using the same best-effort ``_send`` pattern every
prior AI-IOS service established -- **a notification failure never blocks
the operation that triggered it**. A document that processed successfully
but could not tell anyone still processed, and rolling that back because
the mail server was down would turn a cosmetic problem into a real one.

**Every notification names the document and what to do about it.** "OCR
failed" with neither is a message whose only possible response is to go
and look, which the notification was supposed to save.
"""

from __future__ import annotations

from shared_core.enums.notification_channel import NotificationChannel
from shared_core.enums.notification_type import NotificationType
from shared_core.exceptions.notification import NotificationError
from shared_core.logging.logger import get_logger
from shared_core.notifications.manager import NotificationManager

logger = get_logger("app.notifications.document_notifications")

MAX_LISTED_FAILURES = 5
"""How many rule names a notification lists before summarising the rest.
Five fits in a subject-line-sized message; thirty is a wall of text
somebody skims past."""


class DocumentNotificationService:
    """Sends every document-intelligence notification, best-effort."""

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
                "Failed to send a document-intelligence notification.",
                extra={"extra_fields": {"user_id": user_id, "subject": subject}},
            )

    async def send_ocr_failed(
        self, user_id: str, *, title: str, reason: str, pages: int | None = None
    ) -> None:
        """Notify that a document could not be read by OCR.

        The page count is included where known, because "OCR failed" on a
        one-page fax and on a two-hundred-page archive are different
        amounts of work to recover from.
        """
        scope = f" ({pages} page(s))" if pages else ""
        await self._send(
            user_id=user_id,
            subject="An AI-IOS document could not be read by OCR",
            body=f"OCR failed for '{title}'{scope}: {reason}",
            notification_type=NotificationType.ERROR,
        )

    async def send_validation_failed(
        self, user_id: str, *, title: str, failures: list[str]
    ) -> None:
        """Notify that a document failed validation, naming the rules.

        The rule names are the message. A reviewer told only that
        validation failed has to open the document to find out which of
        thirty rules it was.
        """
        listed = ", ".join(failures[:MAX_LISTED_FAILURES]) or "no rule was named"
        more = (
            f" and {len(failures) - MAX_LISTED_FAILURES} more"
            if len(failures) > MAX_LISTED_FAILURES
            else ""
        )
        await self._send(
            user_id=user_id,
            subject="An AI-IOS document failed validation",
            body=f"'{title}' failed validation: {listed}{more}.",
            notification_type=NotificationType.VALIDATION,
        )

    async def send_review_assigned(
        self, user_id: str, *, title: str, reason: str, due_at: str | None = None
    ) -> None:
        """Notify a reviewer that work has been assigned to them.

        Carries the deadline: a review task with no stated deadline is one
        a reviewer has no basis to prioritise against everything else in
        their queue.
        """
        deadline = f" It is due by {due_at}." if due_at else ""
        await self._send(
            user_id=user_id,
            subject="An AI-IOS document needs your review",
            body=f"'{title}' was assigned to you for review: {reason}.{deadline}",
            notification_type=NotificationType.APPROVAL,
        )

    async def send_review_completed(
        self, user_id: str, *, title: str, decision: str, corrections: int
    ) -> None:
        """Notify that a review finished, with the decision and edit count.

        Both, always. "Review completed" alone does not say whether the
        document was approved or rejected, which is the only thing the
        person waiting on it wants to know.
        """
        edits = (
            "no fields were corrected"
            if not corrections
            else f"{corrections} field(s) were corrected"
        )
        await self._send(
            user_id=user_id,
            subject=f"An AI-IOS document review finished: {decision}",
            body=f"'{title}' was reviewed with decision '{decision}'; {edits}.",
            notification_type=NotificationType.SUCCESS,
        )

    async def send_processing_completed(
        self,
        user_id: str,
        *,
        title: str,
        failed_stages: list[str],
        requires_review: bool,
    ) -> None:
        """Notify that processing finished, saying honestly how well.

        A run with failed stages is reported as a warning naming them, not
        as a success: "processing completed" over a document whose tables
        and entities both failed is technically true and practically a
        lie.
        """
        if failed_stages:
            await self._send(
                user_id=user_id,
                subject="An AI-IOS document processed with failures",
                body=(
                    f"'{title}' finished processing, but these stages failed: "
                    f"{', '.join(failed_stages)}."
                ),
                notification_type=NotificationType.WARNING,
            )
            return
        follow_up = " It needs review before use." if requires_review else ""
        await self._send(
            user_id=user_id,
            subject="An AI-IOS document finished processing",
            body=f"'{title}' processed successfully.{follow_up}",
            notification_type=NotificationType.SUCCESS,
        )

    async def send_translation_completed(
        self,
        user_id: str,
        *,
        title: str,
        target_language: str,
        is_faithful: bool = True,
    ) -> None:
        """Notify that a translation is ready, flagging any lost terms.

        An unfaithful translation is announced as a warning rather than a
        completion: the backend dropped protected text, so the output is
        missing content the source had, and nobody should read it as
        finished work.
        """
        if not is_faithful:
            await self._send(
                user_id=user_id,
                subject=f"An AI-IOS translation into {target_language} is incomplete",
                body=(
                    f"'{title}' was translated into {target_language}, but some "
                    "protected terms did not survive and are missing from the output."
                ),
                notification_type=NotificationType.WARNING,
            )
            return
        await self._send(
            user_id=user_id,
            subject=f"An AI-IOS translation into {target_language} is ready",
            body=f"'{title}' was translated into {target_language}.",
            notification_type=NotificationType.SUCCESS,
        )


__all__ = ["MAX_LISTED_FAILURES", "DocumentNotificationService"]
