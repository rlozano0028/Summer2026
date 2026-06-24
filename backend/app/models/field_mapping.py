"""Pydantic models for the Phase 5 field-mapping engine.

Phase 5 turns the Phase 4 prototype mapper into an explainable, testable engine.
These models describe:

- :class:`FieldContext` - enriched, normalized metadata for one detected field.
- :class:`FieldCategory` - the known categories a field can be classified into.
- :class:`MatchEvidence` - one piece of evidence for a classification decision.
- :class:`FieldClassification` - the classifier's decision for one field.
- :class:`ProfileValueResolution` - whether/where a profile value exists.
- :class:`MappingOverride` - a local, user-controlled mapping override.
- :class:`FieldMappingDecision` - the full, explainable decision for one field.

Privacy: nothing in this module stores a full private profile value. Previews
are always redacted/shortened by the redaction service.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FieldCategory(str, Enum):
    """Known categories a detected field can be classified into.

    ``sensitive.*`` categories are never autofilled by Phase 5; they are always
    routed to manual review. ``unknown`` means no confident classification.
    """

    IDENTITY_FIRST_NAME = "identity.first_name"
    IDENTITY_LAST_NAME = "identity.last_name"
    IDENTITY_FULL_NAME = "identity.full_name"
    IDENTITY_EMAIL = "identity.email"
    IDENTITY_PHONE = "identity.phone"
    IDENTITY_CITY = "identity.city"
    IDENTITY_STATE = "identity.state"
    IDENTITY_COUNTRY = "identity.country"

    LINKS_LINKEDIN = "links.linkedin"
    LINKS_GITHUB = "links.github"
    LINKS_PORTFOLIO = "links.portfolio"

    SKILLS_PROGRAMMING_LANGUAGES = "skills.programming_languages"
    SKILLS_FRAMEWORKS = "skills.frameworks"
    SKILLS_TOOLS = "skills.tools"
    SKILLS_DATABASES = "skills.databases"
    SKILLS_CLOUD = "skills.cloud"
    SKILLS_COMBINED = "skills.combined"

    EDUCATION_SCHOOL = "education.school"
    EDUCATION_DEGREE = "education.degree"
    EDUCATION_MAJOR = "education.major"

    EXPERIENCE_COMPANY = "experience.company"
    EXPERIENCE_TITLE = "experience.title"

    RESUME_FILE = "resume.file"

    CUSTOM_COVER_LETTER = "custom.cover_letter"
    CUSTOM_SHORT_ANSWER = "custom.short_answer"

    SENSITIVE_WORK_AUTHORIZATION = "sensitive.work_authorization"
    SENSITIVE_SPONSORSHIP = "sensitive.sponsorship"
    SENSITIVE_SALARY = "sensitive.salary"
    SENSITIVE_DEMOGRAPHIC = "sensitive.demographic"
    SENSITIVE_DISABILITY = "sensitive.disability"
    SENSITIVE_VETERAN = "sensitive.veteran"
    SENSITIVE_LEGAL_ACKNOWLEDGMENT = "sensitive.legal_acknowledgment"
    SENSITIVE_CRIMINAL_HISTORY = "sensitive.criminal_history"

    UNKNOWN = "unknown"


# Categories that must never be autofilled (always manual review).
SENSITIVE_CATEGORIES: frozenset[str] = frozenset(
    {
        FieldCategory.SENSITIVE_WORK_AUTHORIZATION.value,
        FieldCategory.SENSITIVE_SPONSORSHIP.value,
        FieldCategory.SENSITIVE_SALARY.value,
        FieldCategory.SENSITIVE_DEMOGRAPHIC.value,
        FieldCategory.SENSITIVE_DISABILITY.value,
        FieldCategory.SENSITIVE_VETERAN.value,
        FieldCategory.SENSITIVE_LEGAL_ACKNOWLEDGMENT.value,
        FieldCategory.SENSITIVE_CRIMINAL_HISTORY.value,
    }
)


class FieldContext(BaseModel):
    """Enriched, normalized view of one detected field.

    Built from a raw :class:`~app.models.automation.FormField`. ``field_text`` is
    the human-readable combination of all metadata; ``normalized_text`` is the
    lowercased, punctuation-normalized version used for matching.
    """

    field_id: str
    selector: str
    tag_name: str
    input_type: Optional[str] = None
    field_text: str = ""
    normalized_text: str = ""
    label_text: Optional[str] = None
    nearby_text: Optional[str] = None
    placeholder: Optional[str] = None
    name: Optional[str] = None
    id_attribute: Optional[str] = None
    aria_label: Optional[str] = None
    autocomplete: Optional[str] = None
    options: list[str] = Field(default_factory=list)
    required: bool = False
    visible: bool = True
    disabled: bool = False
    readonly: bool = False
    is_file_upload: bool = False
    is_submit_control: bool = False
    is_textarea: bool = False
    is_select: bool = False
    is_checkbox: bool = False
    is_radio: bool = False


class MatchEvidence(BaseModel):
    """One piece of evidence supporting (or contradicting) a classification."""

    # source: label | placeholder | name | id | aria_label | autocomplete |
    #         nearby_text | option_text | override
    source: str
    matched_text: str
    matched_rule: str
    weight: float


class FieldClassification(BaseModel):
    """The classifier's decision for one field, with evidence."""

    field_id: str
    category: str = FieldCategory.UNKNOWN.value
    confidence: float = 0.0
    evidence: list[MatchEvidence] = Field(default_factory=list)
    sensitive: bool = False
    sensitive_reason: Optional[str] = None
    ambiguous: bool = False
    ambiguity_reason: Optional[str] = None


class ProfileValueResolution(BaseModel):
    """Whether a profile value exists for a category, plus a redacted preview."""

    category: str
    profile_path: Optional[str] = None
    value_exists: bool = False
    value_preview: Optional[str] = None
    redacted: bool = False
    missing_reason: Optional[str] = None


class MappingOverride(BaseModel):
    """A local, user-controlled override for one field on one form.

    ``field_fingerprint`` is a stable hash of non-private field metadata so the
    override can be re-applied to the same field on future runs. No profile
    values are ever stored here.
    """

    override_id: str
    form_name: str
    field_fingerprint: str
    category: str
    profile_path: Optional[str] = None
    # action: fill | suggest | manual_review | skip
    action: str
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FieldMappingDecision(BaseModel):
    """The full, explainable mapping decision for one field.

    This is the richest representation. The Phase 4 :class:`FieldMapping` model
    (in :mod:`app.models.automation`) is kept as the wire/plan model for
    backward compatibility and now carries the same enriched fields
    (``category``, ``evidence``, ``warnings``).
    """

    field_id: str
    selector: str
    category: str = FieldCategory.UNKNOWN.value
    profile_path: Optional[str] = None
    value_preview: Optional[str] = None
    confidence: float = 0.0
    # action: fill | suggest | manual_review | skip
    action: str
    sensitive: bool = False
    missing_value: bool = False
    evidence: list[MatchEvidence] = Field(default_factory=list)
    reason: str = ""
    warnings: list[str] = Field(default_factory=list)
