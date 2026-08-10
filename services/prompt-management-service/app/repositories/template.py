"""Repositories for :class:`~app.models.template.PromptTemplate`,
:class:`~app.models.template.PromptVariable`,
:class:`~app.models.template.PromptCategoryRecord`, and
:class:`~app.models.template.PromptTag`.
"""

from __future__ import annotations

from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import (
    PromptCategoryRecord,
    PromptTag,
    PromptTemplate,
    PromptVariable,
)


class PromptTemplateRepository(BaseRepository[PromptTemplate]):
    """CRUD plus lookup for :class:`PromptTemplate`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptTemplate, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, template_id: UUID) -> PromptTemplate:
        """Return *template_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such template exists in that organization.
        """
        stmt = self._base_select().where(
            PromptTemplate.id == template_id,
            PromptTemplate.organization_id == organization_id,
        )
        result = await self._session.execute(stmt)
        found: PromptTemplate | None = result.scalars().first()
        if found is None:
            raise NotFoundError(
                f"PromptTemplate {template_id!s} was not found in organization "
                f"{organization_id!s}."
            )
        return found

    async def get_by_slug(
        self, organization_id: UUID, slug: str, *, locale: str = "en"
    ) -> PromptTemplate | None:
        """One template by slug and locale, or ``None``.

        Locale is part of the natural key rather than a filter applied
        afterwards -- the same slug in two languages is two distinct
        templates ("TEMPLATE MANAGEMENT": Localization).
        """
        stmt = self._base_select().where(
            PromptTemplate.organization_id == organization_id,
            PromptTemplate.slug == slug,
            PromptTemplate.locale == locale,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_by_slug_any_locale(
        self, organization_id: UUID, slug: str, *, preferred_locale: str = "en"
    ) -> PromptTemplate | None:
        """One template by slug, preferring *preferred_locale*.

        The fallback a render needs: a composition referencing a shared
        component by slug should still resolve when that component has
        not been translated yet, rather than failing the whole render
        over a missing locale.
        """
        exact = await self.get_by_slug(organization_id, slug, locale=preferred_locale)
        if exact is not None:
            return exact
        stmt = self._base_select().where(
            PromptTemplate.organization_id == organization_id, PromptTemplate.slug == slug
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_org(
        self, organization_id: UUID, *, limit: int = 200, offset: int = 0
    ) -> list[PromptTemplate]:
        """Every template in *organization_id*, newest first."""
        stmt = (
            self._base_select()
            .where(PromptTemplate.organization_id == organization_id)
            .order_by(PromptTemplate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_shared_components(self, organization_id: UUID) -> list[PromptTemplate]:
        """Every template marked reusable as a shared component."""
        stmt = self._base_select().where(
            PromptTemplate.organization_id == organization_id,
            PromptTemplate.is_shared_component.is_(True),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class PromptVariableRepository(BaseRepository[PromptVariable]):
    """CRUD plus lookup for :class:`PromptVariable`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptVariable, tenant_scope=tenant_scope)

    async def list_for_version(self, prompt_version_id: UUID) -> list[PromptVariable]:
        """Every variable declared by one revision."""
        stmt = (
            self._base_select()
            .where(PromptVariable.prompt_version_id == prompt_version_id)
            .order_by(PromptVariable.name.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(self, prompt_version_id: UUID, name: str) -> PromptVariable | None:
        """One declared variable by name, or ``None``."""
        stmt = self._base_select().where(
            PromptVariable.prompt_version_id == prompt_version_id,
            PromptVariable.name == name,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_masked_names(self, prompt_version_id: UUID) -> set[str]:
        """Names whose values must never be persisted in the clear.

        Both explicitly masked variables and every secret reference --
        a secret is masked whether or not anyone remembered to tick the
        box, since its whole nature is that it must not be recorded.
        """
        stmt = self._base_select().where(PromptVariable.prompt_version_id == prompt_version_id)
        result = await self._session.execute(stmt)
        return {
            row.name
            for row in result.scalars().all()
            if row.is_masked or row.secret_reference is not None
        }


class PromptCategoryRepository(BaseRepository[PromptCategoryRecord]):
    """CRUD plus lookup for :class:`PromptCategoryRecord`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptCategoryRecord, tenant_scope=tenant_scope)

    async def get_by_slug(self, organization_id: UUID, slug: str) -> PromptCategoryRecord | None:
        """One curated category by slug, or ``None``."""
        stmt = self._base_select().where(
            PromptCategoryRecord.organization_id == organization_id,
            PromptCategoryRecord.slug == slug,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_org(self, organization_id: UUID) -> list[PromptCategoryRecord]:
        """Every curated category in *organization_id*, by name."""
        stmt = (
            self._base_select()
            .where(PromptCategoryRecord.organization_id == organization_id)
            .order_by(PromptCategoryRecord.name.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class PromptTagRepository(BaseRepository[PromptTag]):
    """CRUD plus lookup for :class:`PromptTag`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, PromptTag, tenant_scope=tenant_scope)

    async def list_for_prompt(self, prompt_id: UUID) -> list[PromptTag]:
        """Every tag applied to *prompt_id*."""
        stmt = (
            self._base_select()
            .where(PromptTag.prompt_id == prompt_id)
            .order_by(PromptTag.tag.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_prompt_ids_with_tag(self, organization_id: UUID, tag: str) -> list[UUID]:
        """Every prompt id carrying *tag* -- the indexed query the
        denormalized ``Prompt.tags`` JSON column cannot serve."""
        stmt = self._base_select().where(
            PromptTag.organization_id == organization_id, PromptTag.tag == tag
        )
        result = await self._session.execute(stmt)
        return [row.prompt_id for row in result.scalars().all()]

    async def delete_for_prompt(self, prompt_id: UUID) -> int:
        """Remove every tag from *prompt_id*, returning how many went."""
        stmt = self._base_select().where(PromptTag.prompt_id == prompt_id)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        for row in rows:
            await self._session.delete(row)
        await self._session.flush()
        return len(rows)


__all__ = [
    "PromptCategoryRepository",
    "PromptTagRepository",
    "PromptTemplateRepository",
    "PromptVariableRepository",
]
