"""Document access control (docs/062 "SECURITY & ACCESS CONTROL").

Three independent gates, all of which must pass: **classification**
(is the caller cleared for this sensitivity?), **roles** (is the caller in
an allowed group?), and **project scope** (is the caller inside the
project this document belongs to?).

**Every gate fails closed.** A caller with no stated clearance is treated
as ``PUBLIC``, not as unrestricted; a document whose classification is
unrecognised is treated as the highest sensitivity, not the lowest. The
alternative -- defaulting to permissive when information is missing --
turns any gap in the caller's identity into a disclosure, and the whole
point of a retrieval service is that it reads across a corpus the caller
has never seen and cannot audit.

**Filtering happens before retrieval, never after.** Retrieving first and
hiding the results still lets a caller infer that a matching document
exists, and the count, ranking, and latency all leak. The predicates here
are pushed into the vector query -- see
:meth:`~app.vector_store.pgvector_store.PgVectorStore._apply_scope`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from shared_core.exceptions.authorization import AuthorizationError

from app.models.document import Document
from app.models.enums import ClassificationLevel, classification_rank


@dataclass(frozen=True, slots=True)
class AccessContext:
    """Who is asking, and what they are cleared to see."""

    organization_id: UUID
    user_id: str | None = None
    roles: frozenset[str] = field(default_factory=frozenset)
    clearance: ClassificationLevel = ClassificationLevel.PUBLIC
    """Defaults to ``PUBLIC`` -- the lowest. A caller whose clearance
    nobody stated is cleared for public knowledge only."""
    project_scope_ids: frozenset[UUID] = field(default_factory=frozenset)
    is_administrator: bool = False
    """Bypasses role and project scope, but **not** classification. An
    administrator's job is to manage the corpus, which does not by itself
    entitle them to read every secret in it."""

    @classmethod
    def build(
        cls,
        organization_id: UUID,
        *,
        user_id: str | None = None,
        roles: Sequence[str] = (),
        clearance: ClassificationLevel | str = ClassificationLevel.PUBLIC,
        project_scope_ids: Sequence[UUID] = (),
        is_administrator: bool = False,
    ) -> AccessContext:
        """Build a context from loose values, as an API layer supplies them.

        Raises:
            ValueError: If *clearance* is not a known classification. An
                unrecognised clearance is refused rather than silently
                downgraded, because a typo in a role mapping would
                otherwise present as "this user sees nothing" -- which
                looks like a permissions bug and gets fixed by granting
                more, not less.
        """
        return cls(
            organization_id=organization_id,
            user_id=user_id,
            roles=frozenset(role.strip().lower() for role in roles if role.strip()),
            clearance=ClassificationLevel(str(clearance)),
            project_scope_ids=frozenset(project_scope_ids),
            is_administrator=is_administrator,
        )


class AccessDeniedError(AuthorizationError):
    """Raised when a caller may not see a document.

    A distinct type so the audit trail can record a *denial* rather than a
    miss -- "this was refused" and "this does not exist" are different
    facts, and only one of them is worth investigating.

    **It extends the platform's own ``AuthorizationError``, not
    ``PermissionError``.** ``register_exception_handlers`` maps the AI-IOS
    hierarchy; a bare builtin has no handler, so every refusal would leave
    the API as an unhandled exception -- a 500 that says "internal error"
    about a decision the service made deliberately and correctly. Found by
    the API tests, which see the exception itself rather than whatever a
    catch-all turned it into.
    """


def clearance_allows(context: AccessContext, level: ClassificationLevel | str) -> bool:
    """Whether *context* is cleared for documents at *level*.

    An unrecognised classification returns ``False``: an unknown label is
    treated as maximally sensitive rather than as a level nobody
    restricted.
    """
    try:
        return classification_rank(context.clearance) >= classification_rank(level)
    except ValueError:
        return False


def roles_allow(context: AccessContext, allowed_roles: Sequence[str]) -> bool:
    """Whether *context* holds one of *allowed_roles*.

    An empty list means "any role in the organization" -- restriction is
    opt-in at the document level, and this is the one place where absence
    means permitted. That is safe because the organization scope has
    already been applied by the time this runs: "unrestricted" here means
    unrestricted *within one tenant*, never across tenants.
    """
    if not allowed_roles:
        return True
    if context.is_administrator:
        return True
    wanted = {role.strip().lower() for role in allowed_roles if role.strip()}
    return bool(wanted & context.roles)


def scope_allows(context: AccessContext, project_scope_id: UUID | None) -> bool:
    """Whether *context* is inside the document's project scope.

    ``None`` means organization-wide, which everyone in the tenant sees.
    """
    if project_scope_id is None:
        return True
    if context.is_administrator:
        return True
    return project_scope_id in context.project_scope_ids


def can_read(context: AccessContext, document: Document) -> bool:
    """Whether *context* may read *document*. All gates must pass."""
    return (
        document.organization_id == context.organization_id
        and clearance_allows(context, document.classification)
        and roles_allow(context, document.allowed_roles)
        and scope_allows(context, document.project_scope_id)
    )


def require_read(context: AccessContext, document: Document) -> None:
    """Assert that *context* may read *document*.

    Raises:
        AccessDeniedError: If any gate fails. The message names *which* gate,
            because "access denied" with no reason is unactionable for the
            administrator who has to decide whether to grant a role, raise
            a clearance, or add a project -- and it discloses nothing the
            caller did not already supply about themselves.
    """
    if document.organization_id != context.organization_id:
        raise AccessDeniedError(f"Document {document.id!s} belongs to a different organization.")
    if not clearance_allows(context, document.classification):
        raise AccessDeniedError(
            f"This document is classified {document.classification!s} and the caller "
            f"is cleared for {context.clearance!s}."
        )
    if not roles_allow(context, document.allowed_roles):
        raise AccessDeniedError(
            "This document is restricted to roles the caller does not hold: "
            f"{', '.join(sorted(document.allowed_roles))}."
        )
    if not scope_allows(context, document.project_scope_id):
        raise AccessDeniedError(
            f"This document belongs to project {document.project_scope_id!s}, which "
            "the caller is not a member of."
        )


def filter_readable(context: AccessContext, documents: Sequence[Document]) -> list[Document]:
    """Every document in *documents* that *context* may read.

    Silently drops the rest rather than raising. Used on list endpoints,
    where a caller asking for "my documents" should get the ones they can
    see, not a 403 naming one they cannot.
    """
    return [document for document in documents if can_read(context, document)]


def readable_classifications(context: AccessContext) -> tuple[ClassificationLevel, ...]:
    """Every classification *context* is cleared for, for query pushdown.

    Materialised as an ``IN`` list rather than an ordering comparison
    because classification is stored as a string: ``<= 'restricted'``
    would compare alphabetically and quietly admit ``'confidential'`` and
    ``'internal'`` while excluding ``'secret'`` and ``'public'`` -- a
    plausible-looking predicate that is wrong in both directions.
    """
    ceiling = classification_rank(context.clearance)
    return tuple(level for level in ClassificationLevel if classification_rank(level) <= ceiling)


__all__ = [
    "AccessContext",
    "AccessDeniedError",
    "can_read",
    "clearance_allows",
    "filter_readable",
    "readable_classifications",
    "require_read",
    "roles_allow",
    "scope_allows",
]
