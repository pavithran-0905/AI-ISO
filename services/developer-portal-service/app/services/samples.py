"""Sample projects and their code snippets."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.documentation.engine import TransitionResult, validate_transition
from app.models.enums import ContentStatus, SampleProjectCategory
from app.models.samples import CodeSnippet, SampleProject
from app.repositories.samples import CodeSnippetRepository, SampleProjectRepository


class TransitionRefusedError(Exception):
    def __init__(self, result: TransitionResult) -> None:
        super().__init__(result.detail)
        self.result = result


class SampleProjectService:
    def __init__(self, repo: SampleProjectRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        slug: str,
        title: str,
        description: str = "",
        category: SampleProjectCategory,
        repository_url: str = "",
    ) -> SampleProject:
        return await self._repo.create(
            SampleProject(
                organization_id=organization_id,
                slug=slug,
                title=title,
                description=description,
                category=category,
                repository_url=repository_url,
            )
        )

    async def transition(
        self, sample: SampleProject, *, target: ContentStatus, now: datetime
    ) -> SampleProject:
        result = validate_transition(sample.status, target)
        if not result.is_allowed:
            raise TransitionRefusedError(result)
        sample.status = target
        if target == ContentStatus.PUBLISHED:
            sample.published_at = now
        return await self._repo.update(sample)


class CodeSnippetService:
    def __init__(self, repo: CodeSnippetRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        title: str,
        language: str,
        code: str,
        description: str = "",
        sample_project_id: UUID | None = None,
    ) -> CodeSnippet:
        return await self._repo.create(
            CodeSnippet(
                organization_id=organization_id,
                sample_project_id=sample_project_id,
                title=title,
                language=language,
                code=code,
                description=description,
            )
        )


__all__ = ["CodeSnippetService", "SampleProjectService", "TransitionRefusedError"]
