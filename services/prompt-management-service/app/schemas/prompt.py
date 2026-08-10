"""Request/response shapes for ``/prompts`` (docs/061 "REST APIs")."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    PromptCategory,
    PromptLifecycleStatus,
    PromptType,
    PromptVersionStatus,
    SharingScope,
    TemplateFormat,
    VariableKind,
    VariableType,
    VersionBump,
)


class VariablePayload(BaseModel):
    """One declared variable, as submitted by a caller.

    ``secret_reference`` carries a lookup key, never a value -- the API
    has no field through which a secret's plaintext could be sent here,
    which is deliberate.
    """

    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    kind: VariableKind = VariableKind.STATIC
    value_type: VariableType = VariableType.STRING
    default_value: str | None = None
    required: bool = True
    secret_reference: str | None = Field(default=None, max_length=255)
    computed_expression: str | None = None
    validation_rules: dict[str, Any] = Field(default_factory=dict)
    is_masked: bool = False


class PromptCreateRequest(BaseModel):
    """``POST /prompts``."""

    slug: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    prompt_type: PromptType
    body: str = Field(min_length=1)
    description: str | None = None
    category: PromptCategory = PromptCategory.CUSTOM
    sharing_scope: SharingScope = SharingScope.PRIVATE
    template_format: TemplateFormat = TemplateFormat.PLAIN_TEXT
    owner_id: str | None = Field(default=None, max_length=128)
    tags: list[str] = Field(default_factory=list)
    variables: list[VariablePayload] = Field(default_factory=list)


class PromptUpdateRequest(BaseModel):
    """``PUT /prompts/{id}``. ``None`` leaves a field unchanged.

    Deliberately carries no ``body``: prompt text lives in immutable
    revisions and changes only by adding a new one.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: PromptCategory | None = None
    sharing_scope: SharingScope | None = None
    owner_id: str | None = Field(default=None, max_length=128)
    tags: list[str] | None = None


class VersionCreateRequest(BaseModel):
    """``POST /prompts/{id}/versions``."""

    body: str = Field(min_length=1)
    component: VersionBump = VersionBump.PATCH
    changelog: str | None = None
    template_format: TemplateFormat = TemplateFormat.PLAIN_TEXT
    model_hint: str | None = Field(default=None, max_length=128)
    carry_variables: bool = True
    variables: list[VariablePayload] = Field(default_factory=list)


class PublishRequest(BaseModel):
    """``POST /prompts/{id}/publish``."""

    version_number: str = Field(min_length=1, max_length=32)
    force: bool = False
    """Bypass the publication gate. Recorded in the audit trail as an
    override -- a gate that could be skipped silently would not be a
    gate at all."""


class RollbackRequest(BaseModel):
    """``POST /prompts/{id}/rollback``."""

    version_number: str = Field(min_length=1, max_length=32)


class RenderRequest(BaseModel):
    """``POST /prompts/{id}/render``."""

    variables: dict[str, Any] = Field(default_factory=dict)
    version_number: str | None = Field(default=None, max_length=32)
    locale: str = Field(default="en", max_length=16)


class PromptResponse(BaseModel):
    """One registered prompt."""

    id: UUID
    organization_id: UUID
    slug: str
    name: str
    description: str | None
    prompt_type: PromptType
    category: PromptCategory
    status: PromptLifecycleStatus
    sharing_scope: SharingScope
    current_version_number: str | None
    owner_id: str | None
    tags: list[str]
    forked_from_prompt_id: UUID | None
    execution_count: int
    last_executed_at: datetime | None
    last_reviewed_at: datetime | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionResponse(BaseModel):
    """One immutable revision."""

    id: UUID
    prompt_id: UUID
    version_number: str
    status: PromptVersionStatus
    body: str
    template_format: TemplateFormat
    template_id: UUID | None
    changelog: str | None
    model_hint: str | None
    estimated_tokens: int
    is_current: bool
    published_at: datetime | None
    published_by: str | None
    average_score: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VariableResponse(BaseModel):
    """One declared variable.

    Carries ``secret_reference`` (a lookup key) but never a resolved
    value -- there is no field on this model that could hold one.
    """

    id: UUID
    prompt_version_id: UUID
    name: str
    description: str | None
    kind: VariableKind
    value_type: VariableType
    default_value: str | None
    required: bool
    secret_reference: str | None
    computed_expression: str | None
    validation_rules: dict[str, Any]
    is_masked: bool

    model_config = {"from_attributes": True}


class RenderResponse(BaseModel):
    """A rendered prompt, ready to send to a model.

    ``body`` is the real text including any resolved secret. The masked
    copy is deliberately **not** returned: a caller that wants to record
    the execution posts back through ``/prompts/executions``, and this
    service masks it there. Returning both would invite a caller to log
    the wrong one.
    """

    prompt_id: UUID
    version_number: str
    body: str
    variables_used: list[str]
    masked_variables: list[str]
    estimated_tokens: int


class DiffResponse(BaseModel):
    """A comparison between two revisions."""

    from_version: str
    to_version: str
    bump: str | None
    is_forward: bool
    added_lines: list[str]
    removed_lines: list[str]
    token_delta: int


__all__ = [
    "DiffResponse",
    "PromptCreateRequest",
    "PromptResponse",
    "PromptUpdateRequest",
    "PublishRequest",
    "RenderRequest",
    "RenderResponse",
    "RollbackRequest",
    "VariablePayload",
    "VariableResponse",
    "VersionCreateRequest",
    "VersionResponse",
]
