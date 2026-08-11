"""Repositories for embedding models, vectors, and vector indexes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from shared_core.database.repository import BaseRepository
from shared_core.database.tenant import TenantScope
from shared_core.exceptions.not_found import NotFoundError
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embedding import EmbeddingModel, EmbeddingVector, VectorIndex
from app.models.enums import EmbeddingProvider


class EmbeddingModelRepository(BaseRepository[EmbeddingModel]):
    """CRUD plus lookup for :class:`EmbeddingModel`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EmbeddingModel, tenant_scope=tenant_scope)

    async def require_in_org(self, organization_id: UUID, model_id: UUID) -> EmbeddingModel:
        """Return *model_id*, scoped to *organization_id*.

        Raises:
            NotFoundError: If no such model exists in that organization.
        """
        stmt = self._base_select().where(
            EmbeddingModel.id == model_id, EmbeddingModel.organization_id == organization_id
        )
        found: EmbeddingModel | None = (await self._session.execute(stmt)).scalars().first()
        if found is None:
            raise NotFoundError(
                f"EmbeddingModel {model_id!s} was not found in organization "
                f"{organization_id!s}."
            )
        return found

    async def get_default(self, organization_id: UUID) -> EmbeddingModel | None:
        """This organization's default model, or ``None``."""
        stmt = self._base_select().where(
            EmbeddingModel.organization_id == organization_id,
            EmbeddingModel.is_default.is_(True),
            EmbeddingModel.is_active.is_(True),
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def get_by_name(
        self, organization_id: UUID, provider: EmbeddingProvider, model_name: str
    ) -> EmbeddingModel | None:
        """One registered model by provider and name."""
        stmt = self._base_select().where(
            EmbeddingModel.organization_id == organization_id,
            EmbeddingModel.provider == provider,
            EmbeddingModel.model_name == model_name,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_org(self, organization_id: UUID) -> list[EmbeddingModel]:
        """Every model registered here, defaults first."""
        stmt = (
            self._base_select()
            .where(EmbeddingModel.organization_id == organization_id)
            .order_by(EmbeddingModel.is_default.desc(), EmbeddingModel.model_name.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def clear_default(self, organization_id: UUID) -> int:
        """Demote every current default.

        Two defaults would make "which model does this organization use?"
        depend on row order, and the answer decides which vectors a query
        is compared against.
        """
        stmt = self._base_select().where(
            EmbeddingModel.organization_id == organization_id,
            EmbeddingModel.is_default.is_(True),
        )
        rows = list((await self._session.execute(stmt)).scalars().all())
        for row in rows:
            row.is_default = False
            await self.update(row)
        return len(rows)

    async def record_usage(
        self, model: EmbeddingModel, *, vectors: int, tokens: int, cost_usd: float, moment: datetime
    ) -> EmbeddingModel:
        """Accumulate what one embedding run cost."""
        model.vector_count += vectors
        model.total_tokens_embedded += tokens
        model.total_cost_usd += cost_usd
        model.last_used_at = moment
        return await self.update(model)


class EmbeddingVectorRepository(BaseRepository[EmbeddingVector]):
    """CRUD plus lookup for :class:`EmbeddingVector`.

    Similarity *search* lives in
    :class:`~app.vector_store.pgvector_store.PgVectorStore`, not here.
    This repository owns the row lifecycle -- writing, counting,
    deleting; the store owns the ``<=>`` query and the access filtering
    that must sit in the same WHERE clause as it.
    """

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, EmbeddingVector, tenant_scope=tenant_scope)

    async def get_for_chunk(self, chunk_id: UUID, *, model_name: str) -> EmbeddingVector | None:
        """One chunk's vector under one model, or ``None``."""
        stmt = self._base_select().where(
            EmbeddingVector.document_chunk_id == chunk_id,
            EmbeddingVector.model_name == model_name,
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_document(self, document_id: UUID) -> list[EmbeddingVector]:
        """Every vector belonging to one document."""
        stmt = self._base_select().where(EmbeddingVector.document_id == document_id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def delete_for_document(self, document_id: UUID) -> int:
        """Remove every vector for one document.

        A **hard** delete, unlike ``BaseRepository.delete``'s soft one,
        and for two reasons. A vector is derived data -- it can always be
        regenerated from its chunk -- so there is nothing to recover.
        And a soft-deleted vector still occupies the ANN index while
        being unreturnable, so a corpus that churns would accumulate
        index entries that only ever slow queries down.

        It also keeps this repository in agreement with
        :class:`~app.vector_store.pgvector_store.PgVectorStore`, which
        issues a real ``DELETE``; the two disagreeing about what deletion
        means is how a count and the rows behind it drift apart.
        """
        result = await self._session.execute(
            sql_delete(EmbeddingVector).where(EmbeddingVector.document_id == document_id)
        )
        await self._session.flush()
        return int(result.rowcount or 0)

    async def delete_for_model(self, organization_id: UUID, model_name: str) -> int:
        """Remove every vector under one model.

        What a completed model migration runs once the new vectors are
        in place -- see :class:`~app.models.embedding.EmbeddingVector`
        for why both sets coexist until then.
        """
        result = await self._session.execute(
            sql_delete(EmbeddingVector).where(
                EmbeddingVector.organization_id == organization_id,
                EmbeddingVector.model_name == model_name,
            )
        )
        await self._session.flush()
        return int(result.rowcount or 0)

    async def count_for_org(self, organization_id: UUID, *, model_name: str | None = None) -> int:
        """How many vectors this organization holds."""
        stmt = (
            select(func.count())
            .select_from(EmbeddingVector)
            .where(EmbeddingVector.organization_id == organization_id)
        )
        if model_name is not None:
            stmt = stmt.where(EmbeddingVector.model_name == model_name)
        return int((await self._session.execute(stmt)).scalar_one())

    async def models_in_use(self, organization_id: UUID) -> dict[str, int]:
        """How many vectors sit under each model name.

        More than one entry means a migration is either in progress or
        was abandoned, and the leftovers are storage nothing will ever
        query -- retrieval only ever reads the configured model.
        """
        stmt = (
            select(EmbeddingVector.model_name, func.count())
            .where(EmbeddingVector.organization_id == organization_id)
            .group_by(EmbeddingVector.model_name)
        )
        return {str(name): int(count) for name, count in (await self._session.execute(stmt))}

    async def tokens_in_window(
        self, organization_id: UUID, *, since: datetime, until: datetime
    ) -> tuple[int, float]:
        """``(tokens, cost)`` embedded inside one window."""
        stmt = select(
            func.coalesce(func.sum(EmbeddingVector.token_count), 0),
            func.coalesce(func.sum(EmbeddingVector.cost_usd), 0.0),
        ).where(
            EmbeddingVector.organization_id == organization_id,
            EmbeddingVector.embedded_at >= since,
            EmbeddingVector.embedded_at < until,
        )
        tokens, cost = (await self._session.execute(stmt)).one()
        return int(tokens), float(cost)


class VectorIndexRepository(BaseRepository[VectorIndex]):
    """CRUD plus lookup for :class:`VectorIndex`."""

    def __init__(self, session: AsyncSession, *, tenant_scope: TenantScope | None = None) -> None:
        super().__init__(session, VectorIndex, tenant_scope=tenant_scope)

    async def get_by_name(self, organization_id: UUID, name: str) -> VectorIndex | None:
        """One declared index by name."""
        stmt = self._base_select().where(
            VectorIndex.organization_id == organization_id, VectorIndex.name == name
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def list_for_org(self, organization_id: UUID) -> list[VectorIndex]:
        """Every declared index, newest first."""
        stmt = (
            self._base_select()
            .where(VectorIndex.organization_id == organization_id)
            .order_by(VectorIndex.created_at.desc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def list_unvalidated(self, *, limit: int = 100) -> list[VectorIndex]:
        """Indexes never validated, or not validated recently.

        Backs index validation: a declared index nobody ever confirmed
        exists is indistinguishable from one that silently failed to
        build, and both make retrieval quietly slower.
        """
        stmt = (
            self._base_select()
            .order_by(VectorIndex.last_validated_at.asc().nulls_first())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())


__all__ = [
    "EmbeddingModelRepository",
    "EmbeddingVectorRepository",
    "VectorIndexRepository",
]
