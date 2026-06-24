"""Resolve candidate profile values for a classified field category (Phase 5).

Given a :class:`CandidateProfile` and a :class:`FieldCategory`, this module
returns a :class:`ProfileValueResolution` describing whether a value exists, the
profile path it came from, and a redacted preview. It NEVER returns a value for
sensitive / legal categories or for free-text custom answers, even if the
profile happens to contain related data.

The full (un-redacted) value is only produced by :func:`resolve_raw_value`,
which the Playwright runner calls at fill time. Reports/plans only ever carry
the redacted preview.
"""

from __future__ import annotations

from typing import Optional

from app.models.candidate_profile import CandidateProfile
from app.models.field_mapping import FieldCategory, ProfileValueResolution
from app.services.redaction import redact_profile_value

# Maps a category to the dotted profile path used to resolve the value.
# Categories not present here are intentionally not auto-resolved.
CATEGORY_TO_PROFILE_PATH: dict[str, str] = {
    FieldCategory.IDENTITY_FIRST_NAME.value: "identity.first_name",
    FieldCategory.IDENTITY_LAST_NAME.value: "identity.last_name",
    FieldCategory.IDENTITY_FULL_NAME.value: "identity.full_name",
    FieldCategory.IDENTITY_EMAIL.value: "identity.email",
    FieldCategory.IDENTITY_PHONE.value: "identity.phone",
    FieldCategory.IDENTITY_CITY.value: "identity.city",
    FieldCategory.IDENTITY_STATE.value: "identity.state",
    FieldCategory.IDENTITY_COUNTRY.value: "identity.country",
    FieldCategory.LINKS_LINKEDIN.value: "links.linkedin",
    FieldCategory.LINKS_GITHUB.value: "links.github",
    FieldCategory.LINKS_PORTFOLIO.value: "links.portfolio",
    FieldCategory.SKILLS_PROGRAMMING_LANGUAGES.value: "skills.programming_languages",
    FieldCategory.SKILLS_FRAMEWORKS.value: "skills.frameworks",
    FieldCategory.SKILLS_TOOLS.value: "skills.tools",
    FieldCategory.SKILLS_DATABASES.value: "skills.databases",
    FieldCategory.SKILLS_CLOUD.value: "skills.cloud",
    FieldCategory.SKILLS_COMBINED.value: "skills",  # special combined summary
    FieldCategory.EDUCATION_SCHOOL.value: "education.0.school",
    FieldCategory.EDUCATION_DEGREE.value: "education.0.degree",
    FieldCategory.EDUCATION_MAJOR.value: "education.0.major",
    FieldCategory.EXPERIENCE_COMPANY.value: "experience.0.company",
    FieldCategory.EXPERIENCE_TITLE.value: "experience.0.title",
}

# Categories we deliberately never resolve a value for (free-text or upload).
_NON_RESOLVABLE_REASONS: dict[str, str] = {
    FieldCategory.CUSTOM_COVER_LETTER.value: "Cover letters require a custom written response.",
    FieldCategory.CUSTOM_SHORT_ANSWER.value: "Short-answer questions require a custom response.",
    FieldCategory.RESUME_FILE.value: "Resume upload requires an explicit local file path.",
}


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


def resolve_raw_value(profile: CandidateProfile, profile_path: Optional[str]) -> Optional[str]:
    """Resolve the real (un-redacted) string for a profile path, or None.

    Supports dotted paths with numeric list indices, e.g. ``identity.email`` and
    ``education.0.school``. The special path ``"skills"`` returns the combined
    skills summary. List values are joined with commas. Used by the runner; the
    result is never stored in a report.
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


def resolve_profile_value(
    profile: CandidateProfile, category: str
) -> ProfileValueResolution:
    """Resolve a redacted :class:`ProfileValueResolution` for a category.

    Returns ``value_exists=False`` (with a ``missing_reason``) for unknown,
    sensitive, or non-resolvable (free-text / upload) categories, and for paths
    where the profile simply has no value yet.
    """

    # Free-text / upload categories: never auto-resolve a value.
    if category in _NON_RESOLVABLE_REASONS:
        return ProfileValueResolution(
            category=category,
            value_exists=False,
            missing_reason=_NON_RESOLVABLE_REASONS[category],
        )

    profile_path = CATEGORY_TO_PROFILE_PATH.get(category)
    if profile_path is None:
        # Sensitive, unknown, or anything we intentionally do not resolve.
        return ProfileValueResolution(
            category=category,
            value_exists=False,
            missing_reason="Category is not auto-resolved (sensitive or unknown).",
        )

    raw_value = resolve_raw_value(profile, profile_path)
    if raw_value is None:
        return ProfileValueResolution(
            category=category,
            profile_path=profile_path,
            value_exists=False,
            missing_reason="Profile has no value for this field.",
        )

    preview = redact_profile_value(profile_path, raw_value)
    return ProfileValueResolution(
        category=category,
        profile_path=profile_path,
        value_exists=True,
        value_preview=preview,
        redacted=preview != raw_value,
    )
