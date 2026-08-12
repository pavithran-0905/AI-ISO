"""Original-bytes storage (docs/063 "SECURITY": encrypted document storage).

Every uploaded document's original bytes go to MinIO before anything else
happens to them, and every processing run reads them back.

**Without this the service cannot process a document at all.** The
pipeline needs the original bytes: reconstructing them from a stored
version's extracted *text* only works after a successful parse, so a
document's very first run would have nothing to read. That is not a
degraded mode -- it is a service that can never process anything, which is
exactly what the live end-to-end run found.

**Keys are scoped by organization.** ``{organization}/{document}/{n}`` --
so an object key cannot be guessed across tenants, a listing by prefix
returns one tenant's documents only, and a bucket-level retention rule can
target one organization.

**Bytes are never stored on the local filesystem.** Per
docs/008 "FILES", no service keeps files locally: a replica's disk is not
shared, so a document uploaded to one replica would be invisible to the
worker on another.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from shared_core.exceptions.dependency import DependencyError
from shared_core.logging.logger import get_logger
from shared_core.storage.wrapper import StorageWrapper

logger = get_logger("app.services.storage")

DEFAULT_BUCKET = "aiios-documents"

MAX_KEY_LENGTH = 1_024
"""Matches ``Document.storage_key``'s column width. A key longer than the
column would be silently truncated on write and then never found again."""


@dataclass(frozen=True, slots=True)
class StoredObject:
    """Where a document's bytes live."""

    bucket: str
    key: str
    byte_size: int


class DocumentStorage:
    """Stores and retrieves original document bytes."""

    def __init__(self, wrapper: StorageWrapper, *, bucket: str = DEFAULT_BUCKET) -> None:
        self._wrapper = wrapper
        self._bucket = bucket

    @property
    def bucket(self) -> str:
        return self._bucket

    async def ensure_ready(self) -> None:
        """Create the bucket if it does not exist.

        Called once at startup rather than per upload: ``bucket_exists``
        is a network round trip, and paying it on every upload to learn
        something that changes once in a deployment's lifetime is waste on
        the hottest path in the service.
        """
        await self._wrapper.ensure_bucket(self._bucket)

    def key_for(self, organization_id: UUID, document_id: UUID, version: int) -> str:
        """The object key for one version of one document."""
        key = f"{organization_id!s}/{document_id!s}/v{version}"
        return key[:MAX_KEY_LENGTH]

    async def put(
        self,
        *,
        organization_id: UUID,
        document_id: UUID,
        data: bytes,
        content_type: str | None = None,
        version: int = 1,
    ) -> StoredObject:
        """Store a document's original bytes.

        Raises:
            DependencyError: When the object store is unreachable. Raised
                rather than swallowed: an upload that returned 201 while
                losing the bytes is a document the service will never be
                able to process and nobody will know why.
        """
        key = self.key_for(organization_id, document_id, version)
        await self._wrapper.upload(
            self._bucket, key, data, content_type or "application/octet-stream"
        )
        return StoredObject(bucket=self._bucket, key=key, byte_size=len(data))

    async def get(self, *, bucket: str | None, key: str | None) -> bytes:
        """Read a document's original bytes back.

        Raises:
            DependencyError: When the document has no stored location, or
                the store cannot be reached. A document recorded without a
                storage key is one whose upload half-succeeded, and the
                message says so rather than reporting an empty document.
        """
        if not bucket or not key:
            raise DependencyError(
                "This document has no stored object location, so its original "
                "bytes cannot be read. It was recorded before storage was "
                "configured, or its upload did not complete."
            )
        return await self._wrapper.download(bucket, key)

    async def delete(self, *, bucket: str | None, key: str | None) -> bool:
        """Remove a document's bytes, returning whether anything was removed.

        A missing object is not an error here: deleting a document whose
        bytes are already gone should leave the caller with a deleted
        document, not an exception about the second attempt.
        """
        if not bucket or not key:
            return False
        try:
            await self._wrapper.delete(bucket, key)
        except Exception as error:
            logger.warning(
                "Failed to delete a stored document object.",
                extra={"extra_fields": {"bucket": bucket, "key": key, "error": str(error)}},
            )
            return False
        return True


__all__ = ["DEFAULT_BUCKET", "MAX_KEY_LENGTH", "DocumentStorage", "StoredObject"]
