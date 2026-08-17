"""Code playground sessions, saved GraphQL queries, and webhook tests."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.explorer.engine import classify_webhook_response, is_well_formed_graphql_query
from app.models.enums import PlaygroundExampleType, PlaygroundSessionStatus
from app.models.explorer import GraphQlQuery, PlaygroundSession, WebhookTest
from app.repositories.explorer import (
    GraphQlQueryRepository,
    PlaygroundSessionRepository,
    WebhookTestRepository,
)


class MalformedGraphQlQueryError(Exception):
    """Raised when a saved GraphQL query fails the portal's own
    structural sanity check."""


class PlaygroundService:
    def __init__(self, repo: PlaygroundSessionRepository) -> None:
        self._repo = repo

    async def start(
        self,
        organization_id: UUID,
        *,
        user_id: str,
        example_type: PlaygroundExampleType,
        now: datetime,
    ) -> PlaygroundSession:
        return await self._repo.create(
            PlaygroundSession(
                organization_id=organization_id,
                user_id=user_id,
                example_type=example_type,
                started_at=now,
                last_active_at=now,
            )
        )

    async def run(
        self, session: PlaygroundSession, *, code: str, output: str, now: datetime
    ) -> PlaygroundSession:
        session.code = code
        session.output = output
        session.last_active_at = now
        return await self._repo.update(session)

    async def expire(self, session: PlaygroundSession) -> PlaygroundSession:
        session.status = PlaygroundSessionStatus.EXPIRED
        return await self._repo.update(session)


class GraphQlQueryService:
    def __init__(self, repo: GraphQlQueryRepository) -> None:
        self._repo = repo

    async def save(
        self,
        organization_id: UUID,
        *,
        user_id: str,
        name: str,
        query_text: str,
        variables: dict[str, Any] | None = None,
    ) -> GraphQlQuery:
        """Save a GraphQL explorer query, raising
        :class:`MalformedGraphQlQueryError` if it fails the portal's own
        structural sanity check."""
        if not is_well_formed_graphql_query(query_text):
            raise MalformedGraphQlQueryError(
                f"{query_text!r} is not a well-formed GraphQL document."
            )
        return await self._repo.create(
            GraphQlQuery(
                organization_id=organization_id,
                user_id=user_id,
                name=name,
                query_text=query_text,
                variables=variables or {},
                is_saved=True,
            )
        )


class WebhookTestService:
    def __init__(self, repo: WebhookTestRepository) -> None:
        self._repo = repo

    async def create(
        self,
        organization_id: UUID,
        *,
        user_id: str,
        target_url: str,
        payload: dict[str, Any],
        signature: str | None = None,
    ) -> WebhookTest:
        return await self._repo.create(
            WebhookTest(
                organization_id=organization_id,
                user_id=user_id,
                target_url=target_url,
                payload=payload,
                signature=signature,
            )
        )

    async def record_result(
        self, test: WebhookTest, *, response_status_code: int, response_body: str, now: datetime
    ) -> WebhookTest:
        """Record the outcome of a webhook test call the caller already
        made (this service does not itself perform outbound HTTP calls
        to arbitrary developer-supplied URLs from within a request
        handler -- the caller reports the outcome, matching the
        caller-reported-outcome pattern established across this
        codebase)."""
        test.status = classify_webhook_response(response_status_code)
        test.response_status_code = response_status_code
        test.response_body = response_body
        test.tested_at = now
        return await self._repo.update(test)


__all__ = [
    "GraphQlQueryService",
    "MalformedGraphQlQueryError",
    "PlaygroundService",
    "WebhookTestService",
]
