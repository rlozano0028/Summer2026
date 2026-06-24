"""Detect sensitive / legal fields that must never be autofilled (Phase 5).

This is intentionally aggressive: any field touching work authorization,
sponsorship, compensation, demographics (EEO), disability, veteran status,
criminal history, legal acknowledgments, government IDs, or date of birth is
flagged sensitive. Sensitive fields are always routed to manual review, even if
the profile happens to contain a value and even if a user override tries to
force a fill.

The public entry point is :func:`detect_sensitive`, which returns a
:class:`SensitiveMatch` describing whether the field is sensitive, which
category it maps to, and a human-readable reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.field_mapping import FieldCategory, FieldContext

# Each rule: (category, human reason, keywords). Order matters - the first
# matching rule wins, so more specific topics come before broader ones.
#
# Multi-word keywords (containing a space) are matched as substrings of the
# normalized text. Single-word keywords are matched against whole tokens to
# avoid false positives like "age" inside "manage" or "race" inside "trace".
_SENSITIVE_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    (
        FieldCategory.SENSITIVE_SPONSORSHIP.value,
        "Visa sponsorship / immigration status",
        (
            "sponsorship",
            "sponsor",
            "visa",
            "require sponsorship",
            "need sponsorship",
        ),
    ),
    (
        FieldCategory.SENSITIVE_WORK_AUTHORIZATION.value,
        "Work authorization / right to work / citizenship eligibility",
        (
            "work authorization",
            "authorized to work",
            "legally authorized",
            "right to work",
            "employment authorization",
            "work permit",
            "citizenship",
            "citizen",
        ),
    ),
    (
        FieldCategory.SENSITIVE_SALARY.value,
        "Compensation / salary expectations",
        (
            "salary",
            "compensation",
            "expected pay",
            "desired pay",
            "pay expectation",
            "expected salary",
            "desired salary",
            "current pay",
        ),
    ),
    (
        FieldCategory.SENSITIVE_VETERAN.value,
        "Veteran / protected veteran status",
        ("veteran", "protected veteran", "military service"),
    ),
    (
        FieldCategory.SENSITIVE_DISABILITY.value,
        "Disability status",
        ("disability", "disabled", "impairment"),
    ),
    (
        FieldCategory.SENSITIVE_CRIMINAL_HISTORY.value,
        "Criminal history / background check",
        (
            "criminal",
            "felony",
            "conviction",
            "convicted",
            "background check",
        ),
    ),
    (
        FieldCategory.SENSITIVE_DEMOGRAPHIC.value,
        "Demographic / EEO self-identification",
        (
            "gender",
            "race",
            "ethnicity",
            "ethnic",
            "demographic",
            "self identify",
            "self identification",
            "sexual orientation",
            "eeo",
            "date of birth",
            "birth date",
            "birthdate",
            "dob",
            "age",
            "social security",
            "ssn",
            "government id",
            "national id",
        ),
    ),
    (
        FieldCategory.SENSITIVE_LEGAL_ACKNOWLEDGMENT.value,
        "Legal acknowledgment / consent / certification",
        (
            "acknowledge",
            "acknowledgment",
            "acknowledgement",
            "consent",
            "i certify",
            "certify",
            "certification",
            "i agree",
            "agree to",
            "terms and conditions",
            "terms of service",
            "legal acknowledgment",
            "authorize the",
        ),
    ),
]


@dataclass(frozen=True)
class SensitiveMatch:
    """Result of sensitive-field detection for one field."""

    sensitive: bool
    category: Optional[str]
    reason: Optional[str]


def _matches(normalized_text: str, keyword: str) -> bool:
    """Match a keyword against the normalized text.

    Multi-word keywords are matched as substrings; single words are matched as
    whole tokens to avoid accidental substring matches.
    """

    if " " in keyword:
        return keyword in normalized_text
    return keyword in normalized_text.split(" ")


def detect_sensitive(context: FieldContext) -> SensitiveMatch:
    """Return whether ``context`` is a sensitive field, and why."""

    normalized = context.normalized_text or ""
    if not normalized:
        return SensitiveMatch(False, None, None)

    for category, reason, keywords in _SENSITIVE_RULES:
        if any(_matches(normalized, kw) for kw in keywords):
            return SensitiveMatch(True, category, reason)
    return SensitiveMatch(False, None, None)
