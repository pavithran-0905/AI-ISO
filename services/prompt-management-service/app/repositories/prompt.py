"""Repositories for :class:`~app.models.prompt.Prompt` and
:class:`~app.models.prompt.PromptVersion`.

``require_in_org`` is named apart from ``BaseRepository``'s own
unscoped ``require_by_id`` deliberately, per the convention every
AI-IOS service follows: the two differ only in whether they enforce
tenant scoping, and a name collision would make an unscoped lookup
look like a scoped one at the call site.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.search import apply_search
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    PromptCategory,
    PromptLifecycleStatus,
    PromptType,
    PromptVersionStatus,
)
from app.models.prompt import Prompt, PromptVersion


class PromptRepository(BaseRepository[Prompt]):
    """CRUD plus lookup for :class:`Prompt`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, Prompt, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, prompt_id: UUID) -> Prompt:
        """Return *prompt_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such prompt exists in that organization.
        """
        stmt = self._base_select().where(
            Prompt.id == prompt_id, Prompt.organization_id == organization_id
        )
        result = await self._session.execute(stmt)
        found: Prompt | None = result.scalars().first()
        if found is None:
            raise NotFoundError(
                f"Prompt {prompt_id!s} was not found in organization {organization_id!s}."
            )
        return found

    async def get_by_slug(self, organization_id: UUID, slug: str) -> Prompt | None:
        """Return the prompt named *slug* in *organization_id*, or ``None``.

        The resolution path every other service uses: prompts are
        referenced by stable slug, never by generated id.
        """
        stmt = self._base_select().where(
            Prompt.organization_id == organization_id, Prompt.slug == slug
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_org(
        self,
        organization_id: UUID,
        *,
        prompt_type: PromptType | None = None,
        category: PromptCategory | None = None,
        status: PromptLifecycleStatus | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[Prompt]:
        """Every prompt in *organization_id*, newest first."""
        stmt = self._base_select().where(Prompt.organization_id == organization_id)
        if prompt_type is not None:
            stmt = stmt.where(Prompt.prompt_type == prompt_type)
        if category is not None:
            stmt = stmt.where(Prompt.category == category)
        if status is not None:
            stmt = stmt.where(Prompt.status == status)
        stmt = stmt.order_by(Prompt.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def search(self, organization_id: UUID, query: str, *, limit: int = 50) -> list[Prompt]:
        """Full-text-ish search over slug, name, and description."""
        base = self._base_select().where(Prompt.organization_id == organization_id)
        stmt = apply_search(base, Prompt, ["slug", "name", "description"], query).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_due_for_review(self, cutoff: datetime, *, limit: int = 200) -> list[Prompt]:
        """Published prompts unreviewed since *cutoff* ("Review Cycle").

        A prompt that has *never* been reviewed counts as due -- a
        ``NULL`` ``last_reviewed_at`` is the strongest possible signal
        that a review is owed, so excluding it would let exactly the
        prompts most needing attention escape the sweep forever.
        """
        stmt = (
            self._base_select()
            .where(
                Prompt.status == PromptLifecycleStatus.PUBLISHED,
                (Prompt.last_reviewed_at.is_(None)) | (Prompt.last_reviewed_at <= cutoff),
            )
            .order_by(Prompt.last_reviewed_at.asc().nulls_first())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_expired(self, moment: datetime, *, limit: int = 200) -> list[Prompt]:
        """Published prompts past their own expiry ("Expiration Policies")."""
        stmt = (
            self._base_select()
            .where(
                Prompt.status == PromptLifecycleStatus.PUBLISHED,
                Prompt.expires_at.is_not(None),
                Prompt.expires_at <= moment,
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_organization_ids(self, *, limit: int = 200) -> list[UUID]:
        """Every organization with at least one prompt.

        Backs the statistics rollup, which must iterate every tenant
        without an organizations table of its own.
        """
        stmt = select(distinct(Prompt.organization_id)).limit(limit)
        result = await self._session.execute(stmt)
        return [row for row in result.scalars().all() if row is not None]

    async def list_in_window(
        self, organization_id: UUID, *, since: datetime, until: datetime
    ) -> list[Prompt]:
        """Prompts created for *organization_id* within one window."""
        stmt = self._base_select().where(
            Prompt.organization_id == organization_id,
            Prompt.created_at >= since,
            Prompt.created_at < until,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class PromptVersionRepository(BaseRepository[PromptVersion]):
    """CRUD plus lookup for :class:`PromptVersion`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptVersion, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, version_id: UUID) -> PromptVersion:
        """Return *version_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such version exists in that organization.
        """
        stmt = self._base_select().where(
            PromptVersion.id == version_id, PromptVersion.organization_id == organization_id
        )
        result = await self._session.execute(stmt)
        found: PromptVersion | None = result.scalars().first()
        if found is None:
            raise NotFoundError(
                f"PromptVersion {version_id!s} was not found in organization "
                f"{organization_id!s}."
            )
        return found

    async def list_for_prompt(self, prompt_id: UUID) -> list[PromptVersion]:
        """Every revision of *prompt_id*, newest first."""
        stmt = (
            self._base_select()
            .where(PromptVersion.prompt_id == prompt_id)
            .order_by(PromptVersion.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_number(self, prompt_id: UUID, version_number: str) -> PromptVersion | None:
        """One specific revision of *prompt_id*, or ``None``."""
        stmt = self._base_select().where(
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.version_number == version_number,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_current(self, prompt_id: UUID) -> PromptVersion | None:
        """The live revision of *prompt_id*, or ``None``.

        Reads ``is_current`` rather than joining back through
        ``Prompt.current_version_number``: one indexed boolean beats a
        string comparison across two tables on the hottest read path in
        this whole service.
        """
        stmt = self._base_select().where(
            PromptVersion.prompt_id == prompt_id, PromptVersion.is_current.is_(True)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def clear_current(self, prompt_id: UUID) -> int:
        """Demote every currently-live revision of *prompt_id*.

        Returns how many rows were demoted. Called immediately before
        promoting a new one, so exactly one revision is ever
        ``is_current`` -- publishing without this would leave two rows
        both claiming to be live and make :meth:`get_current`
        non-deterministic.
        """
        stmt = self._base_select().where(
            PromptVersion.prompt_id == prompt_id, PromptVersion.is_current.is_(True)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        for row in rows:
            row.is_current = False
            row.status = PromptVersionStatus.SUPERSEDED
        await self._session.flush()
        return len(rows)

    async def list_published(self, prompt_id: UUID) -> list[PromptVersion]:
        """Every revision of *prompt_id* that reached publication."""
        stmt = self._base_select().where(
            PromptVersion.prompt_id == prompt_id,
            PromptVersion.status.in_(
                (PromptVersionStatus.PUBLISHED, PromptVersionStatus.SUPERSEDED)
            ),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["PromptRepository", "PromptVersionRepository"]
