"""Ingestion security scanning (docs/062 "SECURITY").

**The threat that matters most here is indirect prompt injection**, and
it is different from the one prompt-management-service defends against.
There, the untrusted text is a prompt someone authored. Here it is a
*document* — fetched from Confluence, a git repository, an S3 bucket, or
uploaded by anyone with permission — which will later be retrieved and
placed inside a model's context as though it were trusted reference
material.

That inverts the trust model. A user typing "ignore previous
instructions" is visible to whoever reads the conversation. A sentence
buried on page 40 of an ingested PDF saying the same thing is invisible
to the user, invisible to the operator, and reaches the model with the
authority of retrieved context. It also fires for *every* query that
happens to retrieve that chunk, not once.

So the patterns below overlap prompt-management-service's, but the
severity reasoning does not: an injection phrase in an ingested document
is a higher-severity finding than the same phrase in an authored prompt,
because nobody chose to put it in front of the model.

**Findings never carry the matched text.** A scan row quoting the secret
it found would put that secret in the database, in every backup of it,
and in any log line rendering the row.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.models.enums import SecurityFinding, SecuritySeverity

_SEVERITY_ORDER: tuple[SecuritySeverity, ...] = (
    SecuritySeverity.INFO,
    SecuritySeverity.LOW,
    SecuritySeverity.MEDIUM,
    SecuritySeverity.HIGH,
    SecuritySeverity.CRITICAL,
)

REDACTION_PLACEHOLDER = "[REDACTED]"

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----.*?"
            r"-----END (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    (
        "connection_string_password",
        re.compile(
            r"(?i)\b(?:postgres|postgresql|mysql|mongodb|redis|amqp)(?:\+\w+)?://"
            r"[^\s:@/]+:([^\s@]+)(?=@)"
        ),
    ),
    (
        "assigned_secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|passwd|token|credential)\b\s*[:=]\s*"
            r"[\"']?([^\s\"',;]{6,})[\"']?"
        ),
    ),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._\-]{16,})")),
)
"""Kept identical to the pattern set every other AI-IOS guardrail module
carries, so a credential detected by one service is detected by all of
them. Divergence here would mean a secret that ai-assistant-service
redacts flows freely through the RAG index."""

_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
)

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
    (
        "new_instructions",
        re.compile(r"(?i)\b(?:new|updated|revised)\s+instructions?\s*[:.]"),
    ),
    (
        "exfiltration_directive",
        re.compile(
            r"(?i)\b(?:send|post|email|forward|upload)\b.{0,40}"
            r"\b(?:to\s+)?https?://|\bcurl\s+https?://"
        ),
    ),
)
"""The last two are specific to *retrieved* content rather than authored
prompts. "New instructions:" reads as document structure to a human
skimming a page and as a directive to a model consuming it; an
exfiltration directive embedded in a document is the classic indirect
attack, where the model is told to POST what it knows to an attacker's
endpoint."""

_UNSAFE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
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
)

_ZERO_WIDTH = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")
"""Zero-width and bidirectional-override characters. In an ingested
document these are an injection technique in their own right: text that
is invisible to a human reviewing the source still reaches the model,
and a right-to-left override can make a displayed sentence read as the
opposite of what is stored."""


@dataclass(frozen=True, slots=True)
class Finding:
    """One thing a scan detected. Never carries the matched text."""

    finding: SecurityFinding
    severity: SecuritySeverity
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "finding": str(self.finding),
            "severity": str(self.severity),
            "detail": self.detail,
        }


@dataclass(slots=True)
class ScanReport:
    """Everything one scan of one document found."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def highest_severity(self) -> SecuritySeverity:
        if not self.findings:
            return SecuritySeverity.INFO
        return max(self.findings, key=lambda f: _SEVERITY_ORDER.index(f.severity)).severity

    @property
    def is_clean(self) -> bool:
        return not self.findings

    @property
    def should_block(self) -> bool:
        """Whether ingestion should be refused outright.

        Only ``CRITICAL``. Anything less is a concern a human should see,
        not a reason to reject a document -- and over-blocking trains
        people to disable the scanner, which is worse than the findings
        it would have caught.
        """
        return self.highest_severity == SecuritySeverity.CRITICAL

    def to_dicts(self) -> list[dict[str, object]]:
        return [finding.to_dict() for finding in self.findings]

    def counts(self) -> dict[str, int]:
        """How many of each finding kind, for the analytics rollup."""
        totals: dict[str, int] = {}
        for finding in self.findings:
            key = str(finding.finding)
            totals[key] = totals.get(key, 0) + 1
        return totals


def detect_secrets(text: str) -> tuple[str, ...]:
    """Names of secret patterns present. Never the values."""
    return tuple(sorted({name for name, pattern in _SECRET_PATTERNS if pattern.search(text)}))


def detect_pii(text: str) -> tuple[str, ...]:
    """Names of PII patterns present. Never the values."""
    return tuple(sorted({name for name, pattern in _PII_PATTERNS if pattern.search(text)}))


def scan_secrets(text: str) -> list[Finding]:
    """Credentials and PII in ingested content.

    A credential is ``CRITICAL``: a document is chunked, embedded,
    indexed, retrieved, and rendered into other services' prompts and
    logs, so a credential inside one has been copied further than any
    rotation can chase. PII is ``MEDIUM`` -- frequently legitimate in a
    real corpus, always worth a human look.
    """
    findings = [
        Finding(
            SecurityFinding.SECRET_DETECTED,
            SecuritySeverity.CRITICAL,
            f"A {name} pattern appears in this document. Ingesting it would copy "
            "the credential into chunks, vectors, and every prompt that later "
            "retrieves it; treat it as compromised and rotate it.",
        )
        for name in detect_secrets(text)
    ]
    findings.extend(
        Finding(
            SecurityFinding.PII_DETECTED,
            SecuritySeverity.MEDIUM,
            f"A {name} pattern appears in this document.",
        )
        for name in detect_pii(text)
    )
    return findings


def scan_injection(text: str) -> list[Finding]:
    """Indirect prompt injection in ingested content.

    ``HIGH`` rather than ``MEDIUM``, and the reason is the inversion this
    module's docstring describes: the person who will be affected never
    sees this text, and it fires on every query that retrieves the chunk.
    """
    return [
        Finding(
            SecurityFinding.PROMPT_INJECTION,
            SecuritySeverity.HIGH,
            f"Injection phrasing detected ({name}). This document will be placed "
            "inside a model's context as trusted reference material, where such "
            "phrasing acts as an instruction the end user never sees.",
        )
        for name, pattern in _INJECTION_PATTERNS
        if pattern.search(text)
    ]


def scan_unsafe(text: str) -> list[Finding]:
    """Instructions that would be dangerous if a model complied."""
    return [
        Finding(
            SecurityFinding.UNSAFE_CONTENT,
            SecuritySeverity.HIGH,
            f"Unsafe instruction detected ({name}).",
        )
        for name, pattern in _UNSAFE_PATTERNS
        if pattern.search(text)
    ]


def scan_encoding(text: str) -> list[Finding]:
    """Invisible characters used to hide content from a human reviewer."""
    hits = _ZERO_WIDTH.findall(text)
    if not hits:
        return []
    return [
        Finding(
            SecurityFinding.ENCODING_ANOMALY,
            SecuritySeverity.MEDIUM,
            f"{len(hits)} zero-width or bidirectional-override character(s) found. "
            "These are invisible to anyone reviewing the source but reach the model "
            "intact, which is how injected text hides from review.",
        )
    ]


def scan(
    text: str,
    *,
    byte_size: int = 0,
    max_bytes: int = 0,
    restricted_keywords: Sequence[str] = (),
) -> ScanReport:
    """Run every ingestion check over one document's extracted text."""
    findings: list[Finding] = []
    findings.extend(scan_secrets(text))
    findings.extend(scan_injection(text))
    findings.extend(scan_unsafe(text))
    findings.extend(scan_encoding(text))
    findings.extend(scan_restricted(text, restricted_keywords))

    if max_bytes and byte_size > max_bytes:
        findings.append(
            Finding(
                SecurityFinding.OVERSIZED,
                SecuritySeverity.LOW,
                f"Document is {byte_size} bytes, over the {max_bytes}-byte limit.",
            )
        )
    return ScanReport(findings=findings)


def _keyword_pattern(keyword: str) -> str:
    """A literal pattern with boundaries only where the keyword allows.

    ``\\b`` sits between a word and a non-word character, so an
    unconditional ``\\b{kw}\\b`` can never match a term like ``c++`` or
    ``node.js`` -- the trailing boundary would need a word character on
    both sides of a ``+``. An organization configuring such a term would
    get silent non-matching rather than protection, which is the worst of
    the three possible outcomes.
    """
    escaped = re.escape(keyword)
    prefix = r"\b" if keyword[0].isalnum() or keyword[0] == "_" else ""
    suffix = r"\b" if keyword[-1].isalnum() or keyword[-1] == "_" else ""
    return f"{prefix}{escaped}{suffix}"


def scan_restricted(text: str, keywords: Sequence[str]) -> list[Finding]:
    """Organization-configured restricted terms."""
    lowered = text.lower()
    return [
        Finding(
            SecurityFinding.UNSAFE_CONTENT,
            SecuritySeverity.HIGH,
            f"Restricted keyword {keyword.strip()!r} appears in this document.",
        )
        for keyword in keywords
        if keyword.strip() and re.search(_keyword_pattern(keyword.strip().lower()), lowered)
    ]


def redact(text: str) -> tuple[str, tuple[str, ...]]:
    """Replace secret and PII matches, returning the text and what was hit.

    Used on the ingestion path when redaction is enabled, and on query
    text before it is recorded in ``retrieval_queries`` -- search queries
    are sensitive and this table accumulates them.

    Capture groups matter here: ``assigned_secret`` matches
    ``api_key: sk-...`` but only the value is replaced, so the redacted
    text still reads as ``api_key: [REDACTED]``. Replacing the whole
    match would destroy the surrounding context that makes the document
    comprehensible.
    """
    redacted = text
    hit: list[str] = []
    for name, pattern in (*_SECRET_PATTERNS, *_PII_PATTERNS):
        if not pattern.search(redacted):
            continue
        hit.append(name)
        if pattern.groups:
            redacted = pattern.sub(
                lambda match: match.group(0).replace(match.group(1), REDACTION_PLACEHOLDER),
                redacted,
            )
        else:
            redacted = pattern.sub(REDACTION_PLACEHOLDER, redacted)
    return redacted, tuple(sorted(set(hit)))


def strip_invisible(text: str) -> str:
    """Remove zero-width and bidi-override characters.

    Applied to extracted text before chunking when redaction is on:
    leaving them in means embedding characters that carry no meaning and
    can carry an attack.
    """
    return _ZERO_WIDTH.sub("", text)


__all__ = [
    "REDACTION_PLACEHOLDER",
    "Finding",
    "ScanReport",
    "detect_pii",
    "detect_secrets",
    "redact",
    "scan",
    "scan_encoding",
    "scan_injection",
    "scan_restricted",
    "scan_secrets",
    "scan_unsafe",
    "strip_invisible",
]
