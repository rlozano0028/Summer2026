"""Pydantic models describing a structured candidate profile (Phase 1).

Design notes:
- Unknown information is represented as ``None`` (for scalars) or an empty
  list (for collections). "Unknown" is intentionally different from a
  negative answer such as ``False``.
- Sensitive / legal fields (work authorization, sponsorship, salary, etc.)
  default to ``None`` so the system never silently assumes an answer. These
  fields are meant to be confirmed by the user before being used to fill any
  job application.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# Bump this whenever the deterministic parser logic changes in a way that
# affects the shape or meaning of produced profiles.
PARSER_VERSION = "0.1.0"


class Identity(BaseModel):
    """Basic identifying information about the candidate."""

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None


class Links(BaseModel):
    """Online presence / professional links."""

    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None
    other_links: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    """A single education entry (school / degree)."""

    school: Optional[str] = None
    degree: Optional[str] = None
    major: Optional[str] = None
    minor: Optional[str] = None
    start_month: Optional[int] = None
    start_year: Optional[int] = None
    end_month: Optional[int] = None
    end_year: Optional[int] = None
    gpa: Optional[float] = None
    location: Optional[str] = None
    honors: list[str] = Field(default_factory=list)
    coursework: list[str] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    """A single work / professional experience entry."""

    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    start_month: Optional[int] = None
    start_year: Optional[int] = None
    end_month: Optional[int] = None
    end_year: Optional[int] = None
    # ``current`` is None when unknown, not False.
    current: Optional[bool] = None
    bullets: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    """A single project entry."""

    name: Optional[str] = None
    description: Optional[str] = None
    bullets: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class Skills(BaseModel):
    """Grouped skill lists. Empty list means "none detected", not "none"."""

    programming_languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    cloud: list[str] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list)


class WorkAuthorization(BaseModel):
    """Sensitive legal fields.

    These default to ``None`` because an unknown authorization status must
    never be auto-filled as a definitive "yes" or "no". The user must review
    and confirm these before they are used anywhere.
    """

    authorized_to_work_us: Optional[bool] = None
    requires_sponsorship: Optional[bool] = None
    notes: Optional[str] = None


class Preferences(BaseModel):
    """Candidate job preferences.

    ``salary_expectation`` is intentionally free-form and should be treated as
    user-review-required: never auto-fill it without explicit confirmation.
    """

    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: Optional[str] = None
    start_date: Optional[str] = None
    salary_expectation: Optional[str] = None


class Metadata(BaseModel):
    """Bookkeeping about how/when this profile was produced."""

    source_file_name: Optional[str] = None
    source_file_type: Optional[str] = None
    extracted_at: Optional[datetime] = None
    parser_version: str = PARSER_VERSION
    # The deterministic parser always sets this True; it defaults to False so a
    # manually constructed profile is not falsely flagged.
    needs_review: bool = False
    review_notes: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    """Top-level structured profile assembled from a resume."""

    identity: Identity = Field(default_factory=Identity)
    links: Links = Field(default_factory=Links)
    education: list[EducationItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    skills: Skills = Field(default_factory=Skills)
    work_authorization: WorkAuthorization = Field(default_factory=WorkAuthorization)
    preferences: Preferences = Field(default_factory=Preferences)
    metadata: Metadata = Field(default_factory=Metadata)
