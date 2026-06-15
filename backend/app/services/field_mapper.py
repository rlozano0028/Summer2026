"""Deterministic mapping from detected form fields to profile values (Phase 4).

This module is intentionally rule-based and explainable. It does NOT use AI and
never guesses a value the profile does not contain. Sensitive / legal fields are
always routed to manual review.

Public API:
- :func:`map_field_to_profile` - decide what to do with a single field.
- :func:`build_fill_plan` - map every field and summarize the result.
- :func:`resolve_fill_value` - resolve the real (un-redacted) value the runner
  should type, given a profile path. The runner uses this; reports never do.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.models.automation import (
    ACTION_FILL,
    ACTION_MANUAL_REVIEW,
    ACTION_SKIP,
    ACTION_SUGGEST,
    FieldMapping,
    FillPlan,
    FormField,
)
from app.models.candidate_profile import CandidateProfile

# Confidence thresholds (shared with the docs).
FILL_THRESHOLD = 0.90
SUGGEST_THRESHOLD = 0.60

# Keyword sets for sensitive / legal fields. Matching any of these forces
# ``manual_review`` with ``sensitive=True`` and the field is never autofilled.
SENSITIVE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "work_authorization": (
        "work authorization",
        "authorized to work",
        "legally authorized",
        "right to work",
        "employment authorization",
    ),
    "sponsorship": ("sponsorship", "sponsor", "visa"),
    "salary": (
        "salary",
        "compensation",
        "expected pay",
        "desired pay",
        "pay expectation",
    ),
    "demographic_eeo": (
        "gender",
        "race",
        "ethnicity",
        "disability",
        "veteran",
        "demographic",
        "self-identify",
        "self identification",
        "sexual orientation",
        "eeo",
    ),
    "criminal_history": ("criminal", "felony", "conviction", "background check"),
    "legal_acknowledgment": (
        "acknowledge",
        "consent",
        "i certify",
        "i agree",
        "terms and conditions",
        "legal acknowledgment",
    ),
}

# Keywords that identify a resume / CV upload field.
RESUME_KEYWORDS: tuple[str, ...] = ("resume", "cv", "curriculum vitae")

# Keywords that identify a free-text essay / cover-letter field.
ESSAY_KEYWORDS: tuple[str, ...] = (
    "cover letter",
    "why interested",
    "why are you interested",
    "tell us about yourself",
    "about yourself",
    "motivation",
    "essay",
)


class MappingRule:
    """One deterministic field-matching rule."""

    def __init__(
        self,
        keywords: tuple[str, ...],
        profile_path: str,
        confidence: float,
    ) -> None:
        self.keywords = keywords
        self.profile_path = profile_path
        self.confidence = confidence


# Ordered list of mapping rules. Order matters: more specific rules come first
# (e.g. "programming languages" before the generic "skills").
MAPPING_RULES: list[MappingRule] = [
    # Identity (high confidence).
    MappingRule(("first name", "firstname", "given name"), "identity.first_name", 0.95),
    MappingRule(("last name", "lastname", "family name", "surname"), "identity.last_name", 0.95),
    MappingRule(("full name", "fullname"), "identity.full_name", 0.92),
    MappingRule(("email", "e mail"), "identity.email", 0.95),
    MappingRule(("phone", "mobile", "telephone"), "identity.phone", 0.93),
    # Location.
    MappingRule(("city", "town"), "identity.city", 0.92),
    MappingRule(("state", "province"), "identity.state", 0.9),
    MappingRule(("country",), "identity.country", 0.92),
    # Links.
    MappingRule(("linkedin",), "links.linkedin", 0.95),
    MappingRule(("github",), "links.github", 0.95),
    MappingRule(("portfolio", "personal website", "website", "personal site"), "links.portfolio", 0.9),
    # Skill categories (before the generic skills rule).
    MappingRule(("programming language", "programming languages"), "skills.programming_languages", 0.92),
    MappingRule(("framework", "frameworks", "library", "libraries"), "skills.frameworks", 0.92),
    MappingRule(("databases", "database"), "skills.databases", 0.92),
    MappingRule(("cloud", "cloud platform", "cloud platforms"), "skills.cloud", 0.92),
    MappingRule(("tools", "tooling"), "skills.tools", 0.9),
    # Generic combined skills summary.
    MappingRule(("skills", "skill"), "skills", 0.9),
    # Education / experience: deliberately "suggest" (below fill threshold).
    MappingRule(("school", "university", "college", "institution"), "education.0.school", 0.7),
    MappingRule(("degree",), "education.0.degree", 0.7),
    MappingRule(("major", "field of study", "concentration"), "education.0.major", 0.7),
    MappingRule(("company", "employer", "organization"), "experience.0.company", 0.7),
    MappingRule(("job title", "title", "position", "role"), "experience.0.title", 0.7),
]


def _build_haystack(field: FormField) -> str:
    """Combine a field's textual metadata into one lowercase search string.

    Underscores and hyphens are normalized to spaces so ``first_name`` and
    ``given-name`` match the same keywords.
    """

    parts = [
        field.name,
        field.id_attribute,
        field.label_text,
        field.placeholder,
        field.aria_label,
        field.autocomplete,
    ]
    raw = " ".join(p for p in parts if p).lower()
    normalized = raw.replace("_", " ").replace("-", " ")
    return f"{raw} {normalized}"


def _matches_any(haystack: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in haystack for keyword in keywords)


def _combined_skills_summary(profile: CandidateProfile) -> Optional[str]:
    """Return a de-duplicated, comma-separated summary of all skills."""

    skills = profile.skills
    ordered: list[str] = []
    for group in (
        skills.programming_languages,
        skills.frameworks,
        skills.tools,
        skills.databases,
        skills.cloud,
        skills.other,
    ):
        for item in group:
            if item and item not in ordered:
                ordered.append(item)
    return ", ".join(ordered) if ordered else None


def resolve_fill_value(profile: CandidateProfile, profile_path: Optional[str]) -> Optional[str]:
    """Resolve the real string value for a profile path, or None if absent.

    Supports dotted paths with numeric list indices, e.g.
    ``identity.first_name``, ``skills.programming_languages`` (list -> joined),
    and ``education.0.school``. The special path ``"skills"`` returns the
    combined skills summary.
    """

    if not profile_path:
        return None
    if profile_path == "skills":
        return _combined_skills_summary(profile)

    current: object = profile
    for part in profile_path.split("."):
        if part.isdigit():
            index = int(part)
            if not isinstance(current, list) or index >= len(current):
                return None
            current = current[index]
        else:
            current = getattr(current, part, None)
        if current is None:
            return None

    if isinstance(current, list):
        items = [str(item) for item in current if item]
        return ", ".join(items) if items else None
    text = str(current).strip()
    return text or None


def _redact_value(value: str) -> str:
    """Return a shortened / masked preview that never leaks a full value."""

    text = value.strip()
    if not text:
        return ""
    if "@" in text:  # email-like
        local, _, domain = text.partition("@")
        return f"{local[:1]}***@{domain}"
    digit_count = sum(char.isdigit() for char in text)
    if digit_count >= 5:  # phone-like
        return f"***{text[-2:]}"
    if len(text) > 12:
        return f"{text[:12]}\u2026"
    return text


def _skip(field: FormField, reason: str) -> FieldMapping:
    return FieldMapping(
        field_id=field.field_id,
        selector=field.selector,
        action=ACTION_SKIP,
        reason=reason,
    )


def _manual_review(
    field: FormField,
    reason: str,
    *,
    profile_path: Optional[str] = None,
    sensitive: bool = False,
    missing_value: bool = False,
    confidence: float = 0.0,
) -> FieldMapping:
    return FieldMapping(
        field_id=field.field_id,
        selector=field.selector,
        profile_path=profile_path,
        action=ACTION_MANUAL_REVIEW,
        reason=reason,
        sensitive=sensitive,
        missing_value=missing_value,
        confidence=confidence,
    )


def _label_for(field: FormField) -> str:
    """Human-friendly identifier for warnings / summaries."""

    return field.label_text or field.name or field.id_attribute or field.field_id


def map_field_to_profile(field: FormField, profile: CandidateProfile) -> FieldMapping:
    """Decide how to handle a single detected field. Never guesses values."""

    # 1. Submit/buttons and hidden controls are skipped.
    if field.is_submit_control or field.tag_name == "button":
        return _skip(field, "Submit / button control - never autofilled.")
    if field.input_type == "hidden":
        return _skip(field, "Hidden field - skipped.")

    # 2. Disabled / readonly fields cannot be filled.
    if field.disabled or field.readonly:
        return _skip(field, "Field is disabled or readonly.")

    haystack = _build_haystack(field)

    # 3. File uploads: resume uploads need an explicit local path (handled by the
    #    runner), so the deterministic plan always marks them manual_review.
    if field.is_file_upload:
        if _matches_any(haystack, RESUME_KEYWORDS):
            return _manual_review(
                field,
                "Resume upload: provide an explicit local resume file to attach; "
                "left for manual review by default.",
            )
        return _manual_review(field, "File upload left for manual review.")

    # 4. Sensitive / legal fields: always manual review, never autofilled.
    for category, keywords in SENSITIVE_KEYWORDS.items():
        if _matches_any(haystack, keywords):
            return _manual_review(
                field,
                f"Sensitive / legal field ({category.replace('_', ' ')}) - "
                "must be reviewed and answered manually.",
                sensitive=True,
            )

    # 5. Free-text essays / cover letters require a custom answer.
    if field.tag_name == "textarea" or _matches_any(haystack, ESSAY_KEYWORDS):
        return _manual_review(
            field,
            "Free-text answer requires a custom response - left for manual review.",
        )

    # 6. Deterministic value mapping.
    rule = next((r for r in MAPPING_RULES if _matches_any(haystack, r.keywords)), None)
    if rule is None:
        return _manual_review(field, "No deterministic mapping for this field.")

    value = resolve_fill_value(profile, rule.profile_path)
    if value is None:
        return _manual_review(
            field,
            "Profile has no value for this field.",
            profile_path=rule.profile_path,
            missing_value=True,
            confidence=rule.confidence,
        )

    preview = _redact_value(value)
    if rule.confidence >= FILL_THRESHOLD:
        action = ACTION_FILL
        reason = "High-confidence, non-sensitive match - will autofill."
    elif rule.confidence >= SUGGEST_THRESHOLD:
        action = ACTION_SUGGEST
        reason = "Probable match - suggested for review before filling."
    else:
        action = ACTION_MANUAL_REVIEW
        reason = "Low-confidence match - left for manual review."

    return FieldMapping(
        field_id=field.field_id,
        selector=field.selector,
        profile_path=rule.profile_path,
        value_preview=preview,
        confidence=rule.confidence,
        action=action,
        reason=reason,
    )


def build_fill_plan(
    form_name: str,
    form_url: str,
    fields: list[FormField],
    profile: CandidateProfile,
) -> FillPlan:
    """Map every field and summarize the plan with action counts + warnings."""

    mappings = [map_field_to_profile(field, profile) for field in fields]

    counts: dict[str, int] = {
        ACTION_FILL: 0,
        ACTION_SUGGEST: 0,
        ACTION_MANUAL_REVIEW: 0,
        ACTION_SKIP: 0,
    }
    warnings: list[str] = []
    field_by_id = {field.field_id: field for field in fields}
    for mapping in mappings:
        counts[mapping.action] = counts.get(mapping.action, 0) + 1
        field = field_by_id.get(mapping.field_id)
        if field is None:
            continue
        if mapping.sensitive:
            warnings.append(f"Sensitive field left for manual review: {_label_for(field)}")
        elif field.is_file_upload:
            warnings.append(f"File upload left for manual review: {_label_for(field)}")

    return FillPlan(
        form_name=form_name,
        form_url=form_url,
        generated_at=datetime.now(timezone.utc),
        mappings=mappings,
        warnings=warnings,
        fill_count=counts[ACTION_FILL],
        suggest_count=counts[ACTION_SUGGEST],
        manual_review_count=counts[ACTION_MANUAL_REVIEW],
        skip_count=counts[ACTION_SKIP],
    )
