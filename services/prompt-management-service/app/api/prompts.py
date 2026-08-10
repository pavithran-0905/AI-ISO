"""The ``/prompts`` surface (docs/061 "REST APIs" -- the 13 literal
endpoints).

**Registration order inside this router matters.** Every route with a
static path segment (``/test``, ``/evaluate``, ``/optimize``,
``/ab-test``, ``/statistics``, ``/reports``, ``/executions``,
``/reviews``, ``/approvals``) is declared *before*
``GET/PUT/DELETE /{prompt_id}``. FastAPI/Starlette matches in
registration order, and ``{prompt_id}`` is a catch-all at that same
one-segment shape -- declared first it would hijack
``POST /prompts/test`` as ``prompt_id="test"`` and fail UUID parsing
before the request ever reached the handler that owns the path. The
same bug class already found and fixed in notification-center-service,
plugin-marketplace-service, and ai-agent-platform-service.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from shared_core.exceptions.conflict import ConflictError
from shared_core.exceptions.not_found import NotFoundError
from shared_core.logging.context import get_log_context

from app.api.deps import (
    AbSvc,
    AbTestsRepo,
    ApprovalsRepo,
    ApprovalSvc,
    AuditSvc,
    CurrentUserId,
    EvaluationSvc,
    ExecutionSvc,
    Gate,
    OptimizationsRepo,
    OptimizationSvc,
    PromptsRepo,
    PromptSvc,
    RenderingSvc,
    ReportSvc,
    ReviewsRepo,
    ReviewSvc,
    ScansRepo,
    SecuritySvc,
    ServiceSettings,
    StatisticsSvc,
    TestingSvc,
    TestsRepo,
    VariablesRepo,
    VersionsRepo,
)
from app.models.enums import (
    AuditAction,
    PromptCategory,
    PromptLifecycleStatus,
    PromptType,
    ReportKind,
)
from app.models.prompt import PromptVersion
from app.models.template import PromptVariable
from app.schemas.governance import (
    AbTestCreateRequest,
    AbTestResponse,
    ApprovalDecideRequest,
    ApprovalRequestBody,
    ApprovalResponse,
    EvaluateRequest,
    EvaluationResponse,
    ExecutionRecordRequest,
    ExecutionResponse,
    GateResponse,
    OptimizationResponse,
    OptimizeRequest,
    ReportResponse,
    ReviewRequestBody,
    ReviewResponse,
    ReviewSubmitRequest,
    SecurityScanResponse,
    StatisticResponse,
    TestCreateRequest,
    TestResponse,
    TestResultResponse,
    TestRunRequest,
)
from app.schemas.prompt import (
    PromptCreateRequest,
    PromptResponse,
    PromptUpdateRequest,
    PublishRequest,
    RenderRequest,
    RenderResponse,
    RollbackRequest,
    VariablePayload,
    VariableResponse,
    VersionCreateRequest,
    VersionResponse,
)
from app.schemas.response import ResponseMeta, SuccessResponse
from app.security.redaction import redact

router = APIRouter(prefix="/prompts", tags=["Prompts"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=get_log_context().request_id or "unknown")


async def _resolve_version(
    versions: VersionsRepo, prompt_id: UUID, version_number: str | None
) -> PromptVersion:
    """The revision an authoring request means.

    Named version, else the live one, else the newest draft. That last
    fallback matters: a prompt that has never been published has no
    live revision at all, so without it an author could not inspect or
    test the draft they just created -- which is exactly when they need
    to.

    Raises:
        NotFoundError: If the prompt has no such revision, or none at all.
    """
    if version_number is not None:
        version = await versions.get_by_number(prompt_id, version_number)
        if version is None:
            raise NotFoundError(f"This prompt has no version {version_number}.")
        return version

    current = await versions.get_current(prompt_id)
    if current is not None:
        return current

    revisions = await versions.list_for_prompt(prompt_id)
    if not revisions:
        raise NotFoundError("This prompt has no revisions.")
    return revisions[0]


async def _store_variables(
    variables: VariablesRepo,
    organization_id: UUID,
    version_id: UUID,
    payloads: list[VariablePayload],
) -> None:
    """Persist declared variables for one revision."""
    for payload in payloads:
        await variables.create(
            PromptVariable(
                organization_id=organization_id,
                prompt_version_id=version_id,
                name=payload.name,
                description=payload.description,
                kind=payload.kind,
                value_type=payload.value_type,
                default_value=payload.default_value,
                required=payload.required,
                secret_reference=payload.secret_reference,
                computed_expression=payload.computed_expression,
                validation_rules=payload.validation_rules,
                is_masked=payload.is_masked,
            )
        )


# ---- static-segment routes first; see this module's own docstring --------


@router.post(
    "/test",
    response_model=SuccessResponse[TestResponse],
    status_code=201,
    summary="Define a prompt test",
)
async def define_test(
    body: TestCreateRequest, organization_id: UUID, tests: TestingSvc
) -> SuccessResponse[TestResponse]:
    """Register a reusable test case for one prompt."""
    test = await tests.define(
        organization_id=organization_id,
        prompt_id=body.prompt_id,
        name=body.name,
        kind=body.kind,
        description=body.description,
        variables=body.variables,
        expected_output=body.expected_output,
        expected_substrings=body.expected_substrings,
        forbidden_substrings=body.forbidden_substrings,
        minimum_score=body.minimum_score,
    )
    return SuccessResponse(
        message="Test defined.", data=TestResponse.model_validate(test), meta=_meta()
    )


@router.get(
    "/test", response_model=SuccessResponse[list[TestResponse]], summary="List prompt tests"
)
async def list_tests(
    organization_id: UUID,
    tests: TestsRepo,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SuccessResponse[list[TestResponse]]:
    """Tests defined in this organization, newest first."""
    rows = await tests.list_for_org(organization_id, limit=limit, offset=offset)
    return SuccessResponse(
        message="Tests listed.", data=[TestResponse.model_validate(r) for r in rows], meta=_meta()
    )


@router.post(
    "/test/{test_id}/run",
    response_model=SuccessResponse[TestResultResponse],
    status_code=201,
    summary="Run one prompt test",
)
async def run_test(
    test_id: UUID,
    organization_id: UUID,
    body: TestRunRequest,
    tests_repo: TestsRepo,
    versions: VersionsRepo,
    tests: TestingSvc,
    caller: CurrentUserId,
) -> SuccessResponse[TestResultResponse]:
    """Run one case against a revision.

    Raises:
        NotFoundError: If the test or the target revision is absent.
    """
    test = await tests_repo.require_in_org(organization_id, test_id)
    version = await _resolve_version(versions, test.prompt_id, body.version_number)
    result = await tests.run(test, version, actual_output=body.actual_output, run_by=str(caller))
    return SuccessResponse(
        message="Test run.", data=TestResultResponse.model_validate(result), meta=_meta()
    )


@router.post(
    "/evaluate",
    response_model=SuccessResponse[EvaluationResponse],
    status_code=201,
    summary="Evaluate a prompt output",
)
async def evaluate(
    body: EvaluateRequest,
    organization_id: UUID,
    versions: VersionsRepo,
    evaluations: EvaluationSvc,
) -> SuccessResponse[EvaluationResponse]:
    """Score one output against the nine evaluation metrics."""
    version = await versions.require_in_org(organization_id, body.prompt_version_id)
    report = await evaluations.evaluate_output(
        version,
        body.actual,
        expected=body.expected,
        required_points=body.required_points,
        repeated_outputs=body.repeated_outputs,
        grounding=body.grounding,
        latency_ms=body.latency_ms,
        total_tokens=body.total_tokens,
        cost_usd=body.cost_usd,
    )
    return SuccessResponse(
        message="Prompt evaluated.",
        data=EvaluationResponse(
            prompt_version_id=version.id,
            overall=round(report.overall, 4),
            scores=report.to_dicts(),
        ),
        meta=_meta(),
    )


@router.post(
    "/optimize",
    response_model=SuccessResponse[list[OptimizationResponse]],
    status_code=201,
    summary="Analyse a revision for optimizations",
)
async def optimize(
    body: OptimizeRequest,
    organization_id: UUID,
    versions: VersionsRepo,
    optimizations: OptimizationSvc,
) -> SuccessResponse[list[OptimizationResponse]]:
    """Suggest improvements. Nothing is applied -- accepting a
    suggestion creates a new draft through the normal review path."""
    version = await versions.require_in_org(organization_id, body.prompt_version_id)
    stored = await optimizations.analyse(version, min_saving_ratio=body.min_saving_ratio)
    return SuccessResponse(
        message="Optimization analysis complete.",
        data=[OptimizationResponse.model_validate(row) for row in stored],
        meta=_meta(),
    )


@router.post(
    "/optimize/{optimization_id}/accept",
    response_model=SuccessResponse[VersionResponse],
    status_code=201,
    summary="Accept an optimization suggestion",
)
async def accept_optimization(
    optimization_id: UUID,
    organization_id: UUID,
    optimizations_repo: OptimizationsRepo,
    versions: VersionsRepo,
    prompts: PromptsRepo,
    optimizations: OptimizationSvc,
    caller: CurrentUserId,
) -> SuccessResponse[VersionResponse]:
    """Turn a suggestion into a new draft revision."""
    suggestion = await optimizations_repo.require_in_org(organization_id, optimization_id)
    source = await versions.require_in_org(organization_id, suggestion.prompt_version_id)
    prompt = await prompts.require_in_org(organization_id, source.prompt_id)
    version = await optimizations.accept(suggestion, prompt, accepted_by=str(caller))
    return SuccessResponse(
        message="Optimization accepted into a new draft.",
        data=VersionResponse.model_validate(version),
        meta=_meta(),
    )


@router.post(
    "/ab-test",
    response_model=SuccessResponse[AbTestResponse],
    status_code=201,
    summary="Start an A/B experiment",
)
async def start_ab_test(
    body: AbTestCreateRequest,
    organization_id: UUID,
    prompts: PromptsRepo,
    versions: VersionsRepo,
    ab: AbSvc,
) -> SuccessResponse[AbTestResponse]:
    """Split traffic between two revisions of one prompt.

    Raises:
        NotFoundError: If either named revision is absent.
    """
    prompt = await prompts.require_in_org(organization_id, body.prompt_id)
    control = await versions.get_by_number(prompt.id, body.control_version_number)
    variant = await versions.get_by_number(prompt.id, body.variant_version_number)
    if control is None or variant is None:
        raise NotFoundError("Both the control and variant revisions must exist.")

    experiment = await ab.start(
        organization_id=organization_id,
        prompt_id=prompt.id,
        name=body.name,
        control=control,
        variant=variant,
        variant_weight=body.variant_weight,
        minimum_samples_per_arm=body.minimum_samples_per_arm,
        significance_level=body.significance_level,
        auto_promote=body.auto_promote,
    )
    return SuccessResponse(
        message="Experiment started.",
        data=AbTestResponse.model_validate(experiment),
        meta=_meta(),
    )


@router.get(
    "/ab-test",
    response_model=SuccessResponse[list[AbTestResponse]],
    summary="List A/B experiments",
)
async def list_ab_tests(
    organization_id: UUID,
    ab_tests: AbTestsRepo,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SuccessResponse[list[AbTestResponse]]:
    """Experiments in this organization, newest first."""
    rows = await ab_tests.list_for_org(organization_id, limit=limit, offset=offset)
    return SuccessResponse(
        message="Experiments listed.",
        data=[AbTestResponse.model_validate(r) for r in rows],
        meta=_meta(),
    )


@router.post(
    "/executions",
    response_model=SuccessResponse[ExecutionResponse],
    status_code=201,
    summary="Record a prompt execution",
)
async def record_execution(
    body: ExecutionRecordRequest,
    organization_id: UUID,
    prompts: PromptsRepo,
    versions: VersionsRepo,
    variables: VariablesRepo,
    executions: ExecutionSvc,
    caller: CurrentUserId,
) -> SuccessResponse[ExecutionResponse]:
    """Record one production use, reported by whichever service ran it.

    The submitted ``rendered_prompt`` is masked **here** rather than
    trusted to have been masked by the caller: a caller that forgot
    would otherwise write resolved secrets into execution history, and
    this service is the one that knows which variables are sensitive.
    """
    prompt = await prompts.require_in_org(organization_id, body.prompt_id)
    version = await versions.get_by_number(prompt.id, body.version_number)
    if version is None:
        raise NotFoundError(f"Prompt has no version {body.version_number}.")

    masked = redact(body.rendered_prompt).text if body.rendered_prompt else None

    execution = await executions.record(
        prompt,
        version,
        status=body.status,
        masked_prompt=masked,
        model_provider=body.model_provider,
        model_name=body.model_name,
        prompt_tokens=body.prompt_tokens,
        completion_tokens=body.completion_tokens,
        latency_ms=body.latency_ms,
        cost_usd=body.cost_usd,
        executed_by=str(caller),
        agent_id=body.agent_id,
        workflow_id=body.workflow_id,
        ab_test_id=body.ab_test_id,
        ab_arm=str(body.ab_arm) if body.ab_arm else None,
        result_metadata=body.result_metadata,
        error=body.error,
    )
    return SuccessResponse(
        message="Execution recorded.",
        data=ExecutionResponse.model_validate(execution),
        meta=_meta(),
    )


@router.get(
    "/statistics",
    response_model=SuccessResponse[StatisticResponse | None],
    summary="Latest rolled-up prompt activity",
)
async def get_statistics(
    organization_id: UUID, statistics: StatisticsSvc
) -> SuccessResponse[StatisticResponse | None]:
    """This organization's own most recently computed window."""
    windows = await statistics.trend(organization_id, since_days=3_650)
    data = StatisticResponse.model_validate(windows[-1]) if windows else None
    return SuccessResponse(message="Statistics retrieved.", data=data, meta=_meta())


@router.get(
    "/reports", response_model=SuccessResponse[list[ReportResponse]], summary="List reports"
)
async def list_reports(
    organization_id: UUID, reports: ReportSvc, kind: ReportKind | None = None
) -> SuccessResponse[list[ReportResponse]]:
    """Generated reports, newest first."""
    rows = await reports.list_for_org(organization_id, kind=kind)
    return SuccessResponse(
        message="Reports listed.",
        data=[ReportResponse.model_validate(r) for r in rows],
        meta=_meta(),
    )


@router.post(
    "/reports",
    response_model=SuccessResponse[ReportResponse],
    status_code=201,
    summary="Generate a report",
)
async def generate_report(
    organization_id: UUID, kind: ReportKind, reports: ReportSvc, caller: CurrentUserId
) -> SuccessResponse[ReportResponse]:
    """Build one report now."""
    report = await reports.generate(organization_id, kind=kind, generated_by=str(caller))
    return SuccessResponse(
        message="Report generated.", data=ReportResponse.model_validate(report), meta=_meta()
    )


@router.post(
    "/reviews/{review_id}",
    response_model=SuccessResponse[ReviewResponse],
    summary="Submit a review verdict",
)
async def submit_review(
    review_id: UUID,
    organization_id: UUID,
    body: ReviewSubmitRequest,
    reviews_repo: ReviewsRepo,
    reviews: ReviewSvc,
) -> SuccessResponse[ReviewResponse]:
    """Record a reviewer's verdict on a revision."""
    review = await reviews_repo.require_in_org(organization_id, review_id)
    updated = await reviews.submit(
        review,
        decision=body.decision,
        comments=body.comments,
        requested_changes=body.requested_changes,
    )
    return SuccessResponse(
        message="Review submitted.", data=ReviewResponse.model_validate(updated), meta=_meta()
    )


@router.post(
    "/approvals/{approval_id}",
    response_model=SuccessResponse[ApprovalResponse],
    summary="Decide an approval",
)
async def decide_approval(
    approval_id: UUID,
    organization_id: UUID,
    body: ApprovalDecideRequest,
    approvals_repo: ApprovalsRepo,
    approvals: ApprovalSvc,
    caller: CurrentUserId,
) -> SuccessResponse[ApprovalResponse]:
    """Grant or refuse one approval."""
    approval = await approvals_repo.require_in_org(organization_id, approval_id)
    decided = await approvals.decide(
        approval, approver_id=str(caller), approve=body.approve, reason=body.reason
    )
    return SuccessResponse(
        message="Approval decided.", data=ApprovalResponse.model_validate(decided), meta=_meta()
    )


# ---- collection-root routes (no path-arity collision) ---------------------


@router.get("", response_model=SuccessResponse[list[PromptResponse]], summary="List prompts")
async def list_prompts(
    organization_id: UUID,
    prompts: PromptsRepo,
    prompt_type: PromptType | None = None,
    category: PromptCategory | None = None,
    status: PromptLifecycleStatus | None = None,
    query: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SuccessResponse[list[PromptResponse]]:
    """Prompts registered in this organization."""
    rows = (
        await prompts.search(organization_id, query, limit=limit)
        if query
        else await prompts.list_for_org(
            organization_id,
            prompt_type=prompt_type,
            category=category,
            status=status,
            limit=limit,
            offset=offset,
        )
    )
    return SuccessResponse(
        message="Prompts listed.",
        data=[PromptResponse.model_validate(r) for r in rows],
        meta=_meta(),
    )


@router.post(
    "", response_model=SuccessResponse[PromptResponse], status_code=201, summary="Create a prompt"
)
async def create_prompt(
    body: PromptCreateRequest,
    organization_id: UUID,
    prompts: PromptSvc,
    variables: VariablesRepo,
    caller: CurrentUserId,
) -> SuccessResponse[PromptResponse]:
    """Register a prompt and its own first draft revision."""
    prompt, version = await prompts.create(
        organization_id=organization_id,
        slug=body.slug,
        name=body.name,
        prompt_type=body.prompt_type,
        body=body.body,
        description=body.description,
        category=body.category,
        sharing_scope=body.sharing_scope,
        template_format=body.template_format,
        owner_id=body.owner_id,
        tags=body.tags,
        created_by=str(caller),
    )
    await _store_variables(variables, organization_id, version.id, body.variables)
    return SuccessResponse(
        message="Prompt created.", data=PromptResponse.model_validate(prompt), meta=_meta()
    )


# ---- single-prompt routes: the {prompt_id} catch-all and its sub-paths ----


@router.get(
    "/{prompt_id}", response_model=SuccessResponse[PromptResponse], summary="Get one prompt"
)
async def get_prompt(
    prompt_id: UUID, organization_id: UUID, prompts: PromptsRepo
) -> SuccessResponse[PromptResponse]:
    """One registered prompt."""
    prompt = await prompts.require_in_org(organization_id, prompt_id)
    return SuccessResponse(
        message="Prompt retrieved.", data=PromptResponse.model_validate(prompt), meta=_meta()
    )


@router.put(
    "/{prompt_id}", response_model=SuccessResponse[PromptResponse], summary="Update a prompt"
)
async def update_prompt(
    prompt_id: UUID,
    organization_id: UUID,
    body: PromptUpdateRequest,
    prompts_repo: PromptsRepo,
    prompts: PromptSvc,
    caller: CurrentUserId,
) -> SuccessResponse[PromptResponse]:
    """Update one prompt's own identity fields."""
    prompt = await prompts_repo.require_in_org(organization_id, prompt_id)
    updated = await prompts.update(
        prompt,
        name=body.name,
        description=body.description,
        category=body.category,
        sharing_scope=body.sharing_scope,
        owner_id=body.owner_id,
        tags=body.tags,
        updated_by=str(caller),
    )
    return SuccessResponse(
        message="Prompt updated.", data=PromptResponse.model_validate(updated), meta=_meta()
    )


@router.delete(
    "/{prompt_id}", response_model=SuccessResponse[PromptResponse], summary="Archive a prompt"
)
async def archive_prompt(
    prompt_id: UUID,
    organization_id: UUID,
    prompts_repo: PromptsRepo,
    prompts: PromptSvc,
    caller: CurrentUserId,
) -> SuccessResponse[PromptResponse]:
    """Archive one prompt permanently."""
    prompt = await prompts_repo.require_in_org(organization_id, prompt_id)
    archived = await prompts.archive(prompt, archived_by=str(caller))
    return SuccessResponse(
        message="Prompt archived.", data=PromptResponse.model_validate(archived), meta=_meta()
    )


@router.get(
    "/{prompt_id}/versions",
    response_model=SuccessResponse[list[VersionResponse]],
    summary="List a prompt's revisions",
)
async def list_versions(
    prompt_id: UUID, organization_id: UUID, prompts: PromptsRepo, versions: VersionsRepo
) -> SuccessResponse[list[VersionResponse]]:
    """Every revision of one prompt, newest first."""
    prompt = await prompts.require_in_org(organization_id, prompt_id)
    rows = await versions.list_for_prompt(prompt.id)
    return SuccessResponse(
        message="Versions listed.",
        data=[VersionResponse.model_validate(r) for r in rows],
        meta=_meta(),
    )


@router.post(
    "/{prompt_id}/versions",
    response_model=SuccessResponse[VersionResponse],
    status_code=201,
    summary="Add a draft revision",
)
async def add_version(
    prompt_id: UUID,
    organization_id: UUID,
    body: VersionCreateRequest,
    prompts_repo: PromptsRepo,
    prompts: PromptSvc,
    variables: VariablesRepo,
    caller: CurrentUserId,
) -> SuccessResponse[VersionResponse]:
    """Draft a new revision of one prompt."""
    prompt = await prompts_repo.require_in_org(organization_id, prompt_id)
    version = await prompts.add_version(
        prompt,
        body=body.body,
        component=body.component,
        changelog=body.changelog,
        template_format=body.template_format,
        model_hint=body.model_hint,
        created_by=str(caller),
        carry_variables=body.carry_variables,
    )
    await _store_variables(variables, organization_id, version.id, body.variables)
    return SuccessResponse(
        message="Revision drafted.", data=VersionResponse.model_validate(version), meta=_meta()
    )


@router.get(
    "/{prompt_id}/variables",
    response_model=SuccessResponse[list[VariableResponse]],
    summary="List a revision's declared variables",
)
async def list_variables(
    prompt_id: UUID,
    organization_id: UUID,
    prompts: PromptsRepo,
    versions: VersionsRepo,
    variables: VariablesRepo,
    version_number: str | None = None,
) -> SuccessResponse[list[VariableResponse]]:
    """Variables declared by the live revision, or a named one."""
    prompt = await prompts.require_in_org(organization_id, prompt_id)
    version = await _resolve_version(versions, prompt.id, version_number)
    rows = await variables.list_for_version(version.id)
    return SuccessResponse(
        message="Variables listed.",
        data=[VariableResponse.model_validate(r) for r in rows],
        meta=_meta(),
    )


@router.post(
    "/{prompt_id}/publish",
    response_model=SuccessResponse[PromptResponse],
    summary="Publish a revision",
)
async def publish_prompt(
    prompt_id: UUID,
    organization_id: UUID,
    body: PublishRequest,
    prompts_repo: PromptsRepo,
    versions: VersionsRepo,
    prompts: PromptSvc,
    gate: Gate,
    audit: AuditSvc,
    settings: ServiceSettings,
    caller: CurrentUserId,
) -> SuccessResponse[PromptResponse]:
    """Make one revision live, subject to the publication gate.

    ``force`` bypasses the gate but is recorded in the audit trail as
    an override -- a gate that could be skipped silently would not be
    a gate.

    Raises:
        NotFoundError: If the named revision is absent.
        ConflictError: If the gate refuses and ``force`` is not set.
    """
    prompt = await prompts_repo.require_in_org(organization_id, prompt_id)
    version = await versions.get_by_number(prompt.id, body.version_number)
    if version is None:
        raise NotFoundError(f"Prompt has no version {body.version_number}.")

    decision = await gate.evaluate(
        version,
        required_approvals=settings.required_approvals,
        block_on_critical=settings.block_publish_on_critical,
    )
    if not decision.allowed:
        if not body.force:
            raise ConflictError(f"This revision cannot be published. {decision.reason}")
        await audit.record(
            organization_id,
            action=AuditAction.ADMINISTRATIVE,
            entity_type="prompt_version",
            entity_id=version.id,
            entity_reference=f"{prompt.slug}@{version.version_number}",
            actor_id=str(caller),
            summary=f"Publication gate overridden. Blockers: {decision.reason}",
            succeeded=False,
        )

    published = await prompts.publish(prompt, version, published_by=str(caller))
    return SuccessResponse(
        message="Prompt published.", data=PromptResponse.model_validate(published), meta=_meta()
    )


@router.get(
    "/{prompt_id}/gate",
    response_model=SuccessResponse[GateResponse],
    summary="Check the publication gate",
)
async def check_gate(
    prompt_id: UUID,
    organization_id: UUID,
    version_number: str,
    prompts: PromptsRepo,
    versions: VersionsRepo,
    gate: Gate,
    settings: ServiceSettings,
) -> SuccessResponse[GateResponse]:
    """Report every blocker standing between a revision and publication."""
    prompt = await prompts.require_in_org(organization_id, prompt_id)
    version = await versions.get_by_number(prompt.id, version_number)
    if version is None:
        raise NotFoundError(f"Prompt has no version {version_number}.")
    decision = await gate.evaluate(
        version,
        required_approvals=settings.required_approvals,
        block_on_critical=settings.block_publish_on_critical,
    )
    return SuccessResponse(
        message="Gate evaluated.",
        data=GateResponse(
            allowed=decision.allowed, blockers=list(decision.blockers), reason=decision.reason
        ),
        meta=_meta(),
    )


@router.post(
    "/{prompt_id}/rollback",
    response_model=SuccessResponse[PromptResponse],
    summary="Roll back to an earlier revision",
)
async def rollback_prompt(
    prompt_id: UUID,
    organization_id: UUID,
    body: RollbackRequest,
    prompts_repo: PromptsRepo,
    prompts: PromptSvc,
    caller: CurrentUserId,
) -> SuccessResponse[PromptResponse]:
    """Point a prompt back at an earlier published revision."""
    prompt = await prompts_repo.require_in_org(organization_id, prompt_id)
    rolled = await prompts.rollback(
        prompt, to_version_number=body.version_number, rolled_back_by=str(caller)
    )
    return SuccessResponse(
        message="Prompt rolled back.", data=PromptResponse.model_validate(rolled), meta=_meta()
    )


@router.post(
    "/{prompt_id}/render",
    response_model=SuccessResponse[RenderResponse],
    summary="Render a prompt",
)
async def render_prompt(
    prompt_id: UUID,
    organization_id: UUID,
    body: RenderRequest,
    prompts: PromptsRepo,
    rendering: RenderingSvc,
) -> SuccessResponse[RenderResponse]:
    """Resolve and render one prompt for use against a model.

    Secret references are **not** resolved here: no secret resolver is
    wired into the HTTP path, so a render over the API returns the
    placeholder for them. Resolving live secrets requires the caller's
    own authority against secrets-management-service, which is a
    deliberate follow-up rather than something to do implicitly on
    every render.
    """
    prompt = await prompts.require_in_org(organization_id, prompt_id)
    result = await rendering.render(
        organization_id,
        prompt.slug,
        body.variables,
        version_number=body.version_number,
        locale=body.locale,
    )
    return SuccessResponse(
        message="Prompt rendered.",
        data=RenderResponse(
            prompt_id=prompt.id,
            version_number=result.version.version_number,
            body=result.body,
            variables_used=list(result.variables_used),
            masked_variables=sorted(result.masked_names),
            estimated_tokens=result.estimated_tokens,
        ),
        meta=_meta(),
    )


@router.post(
    "/{prompt_id}/scan",
    response_model=SuccessResponse[SecurityScanResponse],
    status_code=201,
    summary="Security-scan a revision",
)
async def scan_prompt(
    prompt_id: UUID,
    organization_id: UUID,
    version_number: str,
    prompts: PromptsRepo,
    versions: VersionsRepo,
    security: SecuritySvc,
    settings: ServiceSettings,
    caller: CurrentUserId,
) -> SuccessResponse[SecurityScanResponse]:
    """Scan one revision for secrets, PII, injection, and unsafe content."""
    prompt = await prompts.require_in_org(organization_id, prompt_id)
    version = await versions.get_by_number(prompt.id, version_number)
    if version is None:
        raise NotFoundError(f"Prompt has no version {version_number}.")
    scan = await security.scan_version(
        version,
        restricted_keywords=settings.restricted_keywords,
        scanned_by=str(caller),
        block_on_critical=settings.block_publish_on_critical,
    )
    return SuccessResponse(
        message="Revision scanned.",
        data=SecurityScanResponse.model_validate(scan),
        meta=_meta(),
    )


@router.get(
    "/{prompt_id}/scans",
    response_model=SuccessResponse[list[SecurityScanResponse]],
    summary="List a revision's scans",
)
async def list_scans(
    prompt_id: UUID,
    organization_id: UUID,
    version_number: str,
    prompts: PromptsRepo,
    versions: VersionsRepo,
    scans: ScansRepo,
) -> SuccessResponse[list[SecurityScanResponse]]:
    """Every scan of one revision, newest first."""
    prompt = await prompts.require_in_org(organization_id, prompt_id)
    version = await versions.get_by_number(prompt.id, version_number)
    if version is None:
        raise NotFoundError(f"Prompt has no version {version_number}.")
    rows = await scans.list_for_version(version.id)
    return SuccessResponse(
        message="Scans listed.",
        data=[SecurityScanResponse.model_validate(r) for r in rows],
        meta=_meta(),
    )


@router.post(
    "/{prompt_id}/reviews",
    response_model=SuccessResponse[ReviewResponse],
    status_code=201,
    summary="Request a review",
)
async def request_review(
    prompt_id: UUID,
    organization_id: UUID,
    body: ReviewRequestBody,
    prompts: PromptsRepo,
    versions: VersionsRepo,
    reviews: ReviewSvc,
) -> SuccessResponse[ReviewResponse]:
    """Ask a named reviewer to review a revision."""
    prompt = await prompts.require_in_org(organization_id, prompt_id)
    version = await versions.get_by_number(prompt.id, body.version_number)
    if version is None:
        raise NotFoundError(f"Prompt has no version {body.version_number}.")
    review = await reviews.request(
        version, reviewer_id=body.reviewer_id, is_mandatory=body.is_mandatory
    )
    return SuccessResponse(
        message="Review requested.", data=ReviewResponse.model_validate(review), meta=_meta()
    )


@router.post(
    "/{prompt_id}/approvals",
    response_model=SuccessResponse[ApprovalResponse],
    status_code=201,
    summary="Open an approval gate",
)
async def request_approval(
    prompt_id: UUID,
    organization_id: UUID,
    body: ApprovalRequestBody,
    prompts: PromptsRepo,
    versions: VersionsRepo,
    approvals: ApprovalSvc,
    settings: ServiceSettings,
    caller: CurrentUserId,
) -> SuccessResponse[ApprovalResponse]:
    """Open an approval gate on a revision."""
    prompt = await prompts.require_in_org(organization_id, prompt_id)
    version = await versions.get_by_number(prompt.id, body.version_number)
    if version is None:
        raise NotFoundError(f"Prompt has no version {body.version_number}.")
    approval = await approvals.request(
        version,
        required_approvals=body.required_approvals,
        expiry_seconds=settings.approval_expiry_seconds,
        requested_by=str(caller),
    )
    return SuccessResponse(
        message="Approval requested.",
        data=ApprovalResponse.model_validate(approval),
        meta=_meta(),
    )


__all__ = ["router"]
