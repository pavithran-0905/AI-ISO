"""Code playground sessions, saved GraphQL queries, and webhook tests."""

from __future__ import annotations

from datetime import datetime

from shared_core.database.base import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.enums import PlaygroundExampleType, PlaygroundSessionStatus, WebhookTestStatus


class PlaygroundSession(BaseModel):
    """``playground_sessions`` -- one interactive code playground
    session."""

    __tablename__ = "playground_sessions"
    __table_args__ = (
        Index("ix_playground_session_user", "user_id"),
        Index("ix_playground_session_status", "status"),
    )

    user_id: Mapped[str] = mapped_column(String(128), index=True)
    example_type: Mapped[PlaygroundExampleType] = mapped_column(String(16), index=True)
    status: Mapped[PlaygroundSessionStatus] = mapped_column(
        String(16), default=PlaygroundSessionStatus.ACTIVE, index=True
    )
    code: Mapped[str] = mapped_column(Text, default="")
    output: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GraphQlQuery(BaseModel):
    """``graphql_queries`` -- one saved (or history-only) GraphQL
    explorer query."""

    __tablename__ = "graphql_queries"
    __table_args__ = (Index("ix_graphql_query_user", "user_id"),)

    user_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    query_text: Mapped[str] = mapped_column(Text)
    variables: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class WebhookTest(BaseModel):
    """``webhook_tests`` -- one simulated webhook delivery run against a
    developer-supplied target URL."""

    __tablename__ = "webhook_tests"
    __table_args__ = (
        Index("ix_webhook_test_user", "user_id"),
        Index("ix_webhook_test_status", "status"),
    )

    user_id: Mapped[str] = mapped_column(String(128), index=True)
    target_url: Mapped[str] = mapped_column(String(1024))
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    signature: Mapped[str | None] = mapped_column(String(128), default=None)
    status: Mapped[WebhookTestStatus] = mapped_column(
        String(16), default=WebhookTestStatus.PENDING, index=True
    )
    response_status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    response_body: Mapped[str] = mapped_column(Text, default="")
    tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


__all__ = ["GraphQlQuery", "PlaygroundSession", "WebhookTest"]
