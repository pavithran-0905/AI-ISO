"""Prompt security scanning (docs/061 "SECURITY").

Grades one prompt body against every check docs/061 names: Prompt
Validation, Secret Detection, PII Detection, Prompt Injection
Detection, Unsafe Instructions, Restricted Keywords, plus the template
syntax and undeclared-variable checks that only make sense for a
templated prompt.

**Severity is what makes this useful rather than noisy.** A secret in
a prompt body is always critical -- a prompt is stored, versioned,
shared, and rendered into logs, so a credential written into one is
already compromised. An email address usually is not critical; it may
be a deliberate example. Grading them identically would either block
every harmless prompt or let a real credential through.

**Findings never carry the matched text** -- see
:mod:`app.security.redaction` for why. A scan row that quoted the
secret it found would put that secret in the database, in backups of
it, and in any log line rendering the row.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.models.enums import ScanStatus, SecurityFinding, SecuritySeverity
from app.security.redaction import detect, is_pii
from app.templating.renderer import declared_variables, validate_syntax

_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ignore_previous", re.compile(r"(?i)\bignore\s+(?:all\s+)?(?:the\s+)?previous\b")),
    (
        "disregard_instructions",
        re.compile(r"(?i)\bdisregard\s+(?:all\s+)?(?:prior|above|previous)\b"),
    ),
    ("forget_instructions", re.compile(r"(?i)\bforget\s+(?:everything|all|your)\b")),
    (
        "reveal_system_prompt",
        re.compile(
            r"(?i)\b(?:reveal|print|show|repeat|output)\s+"
            r"(?:your\s+)?(?:the\s+)?system\s+prompt\b"
        ),
    ),
    ("role_override", re.compile(r"(?i)\byou\s+are\s+now\s+(?:a|an|no longer)\b")),
    ("developer_mode", re.compile(r"(?i)\b(?:developer|god|dan|jailbreak)\s+mode\b")),
    (
        "instruction_delimiter",
        re.compile(r"(?i)^\s*(?:###\s*)?(?:system|assistant)\s*:", re.MULTILINE),
    ),
)
"""Injection phrasings. These are matched against a **prompt template
being authored**, not against end-user input at runtime -- an author
writing "ignore all previous instructions" into a stored, shared prompt
is a different and more serious event than a user typing it, because
the stored version runs for everyone."""

_UNSAFE_INSTRUCTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "credential_exfiltration",
        re.compile(
            r"(?i)\b(?:send|post|upload|email|exfiltrate)\b.{0,40}"
            r"\b(?:credential|password|api[_-]?key|secret|token)s?\b"
        ),
    ),
    (
        "destructive_command",
        re.compile(
            r"(?i)\b(?:rm\s+-rf|drop\s+(?:table|database)|truncate\s+table" r"|shutdown\s+-|mkfs)\b"
        ),
    ),
    (
        "disable_safety",
        re.compile(
            r"(?i)\b(?:disable|bypass|turn\s+off|ignore)\b.{0,30}"
            r"\b(?:safety|guardrail|filter|moderation|restriction)s?\b"
        ),
    ),
    ("arbitrary_execution", re.compile(r"(?i)\b(?:eval|exec|system|popen|subprocess)\s*\(")),
)
"""Instructions that would be dangerous if a model complied. Matched on
the authored template for the same reason as injection patterns."""

_SEVERITY_ORDER: tuple[SecuritySeverity, ...] = (
    SecuritySeverity.INFO,
    SecuritySeverity.LOW,
    SecuritySeverity.MEDIUM,
    SecuritySeverity.HIGH,
    SecuritySeverity.CRITICAL,
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing a scan detected.

    ``detail`` names the *kind* of match and where, never the matched
    value.
    """

    finding: SecurityFinding
    severity: SecuritySeverity
    detail: str

    def to_dict(self) -> dict[str, object]:
        """Render for ``prompt_security_scans.findings``."""
        return {
            "finding": str(self.finding),
            "severity": str(self.severity),
            "detail": self.detail,
        }


@dataclass(slots=True)
class ScanReport:
    """Everything one scan of one prompt body found."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def highest_severity(self) -> SecuritySeverity:
        """The worst severity present, or ``INFO`` when nothing fired."""
        if not self.findings:
            return SecuritySeverity.INFO
        return max(self.findings, key=lambda f: _SEVERITY_ORDER.index(f.severity)).severity

    @property
    def status(self) -> ScanStatus:
        """``CLEAN``, ``FLAGGED``, or ``BLOCKED``.

        ``BLOCKED`` only for ``CRITICAL``: anything less is a concern a
        human should see, not a reason to refuse a publish outright.
        """
        if not self.findings:
            return ScanStatus.CLEAN
        if self.highest_severity == SecuritySeverity.CRITICAL:
            return ScanStatus.BLOCKED
        return ScanStatus.FLAGGED

    def to_dicts(self) -> list[dict[str, object]]:
        """Every finding, rendered for persistence."""
        return [finding.to_dict() for finding in self.findings]


def scan_secrets(body: str) -> list[Finding]:
    """Secret and PII detection.

    Credentials are ``CRITICAL`` -- a prompt is stored, versioned,
    shared, and rendered into logs, so a credential written into one is
    already compromised regardless of what the prompt does next. PII is
    ``MEDIUM``: often a deliberate example, always worth a human look.
    """
    findings: list[Finding] = []
    for kind in detect(body):
        if is_pii(kind):
            findings.append(
                Finding(
                    finding=SecurityFinding.PII_DETECTED,
                    severity=SecuritySeverity.MEDIUM,
                    detail=f"A {kind} pattern appears in the prompt body.",
                )
            )
        else:
            findings.append(
                Finding(
                    finding=SecurityFinding.SECRET_DETECTED,
                    severity=SecuritySeverity.CRITICAL,
                    detail=(
                        f"A {kind} pattern appears in the prompt body. A prompt is "
                        "stored, versioned, and rendered into logs, so treat this "
                        "credential as already compromised and rotate it."
                    ),
                )
            )
    return findings


def scan_injection(body: str) -> list[Finding]:
    """Prompt injection phrasing in an authored template."""
    return [
        Finding(
            finding=SecurityFinding.PROMPT_INJECTION,
            severity=SecuritySeverity.HIGH,
            detail=f"Injection phrasing detected ({name}).",
        )
        for name, pattern in _INJECTION_PATTERNS
        if pattern.search(body)
    ]


def scan_unsafe_instructions(body: str) -> list[Finding]:
    """Instructions that would be dangerous if a model complied."""
    return [
        Finding(
            finding=SecurityFinding.UNSAFE_INSTRUCTION,
            severity=SecuritySeverity.CRITICAL,
            detail=f"Unsafe instruction detected ({name}).",
        )
        for name, pattern in _UNSAFE_INSTRUCTION_PATTERNS
        if pattern.search(body)
    ]


def _keyword_pattern(keyword: str) -> str:
    """A case-folded, literal pattern for one restricted keyword.

    Word boundaries are applied **only where the keyword's own edge is
    a word character**. ``\\b`` sits between a word and a non-word
    character, so an unconditional ``\\b{kw}\\b`` can never match a
    keyword like ``c++`` or ``node.js`` -- the trailing ``\\b`` would
    need a word character on both sides of a ``+``. An organization
    configuring such a term would get silent non-matching rather than
    protection or an error, which is the worst of the three outcomes.
    """
    escaped = re.escape(keyword)
    prefix = r"\b" if keyword[0].isalnum() or keyword[0] == "_" else ""
    suffix = r"\b" if keyword[-1].isalnum() or keyword[-1] == "_" else ""
    return f"{prefix}{escaped}{suffix}"


def scan_restricted_keywords(body: str, keywords: Sequence[str]) -> list[Finding]:
    """Organization-configured restricted terms.

    Matched case-insensitively, on word boundaries where the keyword
    allows one, so a configured term like ``ssn`` does not fire on
    ``assassin`` while ``c++`` still matches at all.
    """
    lowered = body.lower()
    return [
        Finding(
            finding=SecurityFinding.RESTRICTED_KEYWORD,
            severity=SecuritySeverity.HIGH,
            detail=f"Restricted keyword {keyword!r} appears in the prompt body.",
        )
        for keyword in keywords
        if keyword.strip() and re.search(_keyword_pattern(keyword.strip().lower()), lowered)
    ]


def scan_template(body: str, declared: Sequence[str]) -> list[Finding]:
    """Template validity and variable declaration.

    An undeclared variable is ``HIGH``, not cosmetic: rendering runs
    under ``StrictUndefined``, so a variable the template uses but
    nobody declared makes every render of this prompt fail at runtime.
    """
    syntax_error = validate_syntax(body)
    if syntax_error is not None:
        return [
            Finding(
                finding=SecurityFinding.TEMPLATE_SYNTAX_ERROR,
                severity=SecuritySeverity.CRITICAL,
                detail=syntax_error,
            )
        ]

    known = {name.lower() for name in declared}
    return [
        Finding(
            finding=SecurityFinding.UNDECLARED_VARIABLE,
            severity=SecuritySeverity.HIGH,
            detail=(
                f"Template variable {used!r} is used but not declared. Rendering "
                "runs under StrictUndefined, so every render would fail."
            ),
        )
        for used in declared_variables(body)
        if used.lower() not in known
    ]


def scan(
    body: str,
    *,
    declared_variable_names: Sequence[str] = (),
    restricted_keywords: Sequence[str] = (),
) -> ScanReport:
    """Run every security check over one prompt body.

    Template checks run first and short-circuit the rest when the
    syntax is invalid: a body Jinja2 cannot parse cannot be meaningfully
    scanned for anything else, and reporting six downstream findings
    from one broken brace buries the actual problem.
    """
    template_findings = scan_template(body, declared_variable_names)
    if any(f.finding == SecurityFinding.TEMPLATE_SYNTAX_ERROR for f in template_findings):
        return ScanReport(findings=template_findings)

    return ScanReport(
        findings=[
            *scan_secrets(body),
            *scan_injection(body),
            *scan_unsafe_instructions(body),
            *scan_restricted_keywords(body, restricted_keywords),
            *template_findings,
        ]
    )


__all__ = [
    "Finding",
    "ScanReport",
    "scan",
    "scan_injection",
    "scan_restricted_keywords",
    "scan_secrets",
    "scan_template",
    "scan_unsafe_instructions",
]
