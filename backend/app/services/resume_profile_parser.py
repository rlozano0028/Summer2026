"""Deterministic resume -> profile parser (Phase 2).

This is intentionally conservative. It only fills fields it can detect with
simple, explainable rules (regex + keyword matching). It NEVER invents schools,
companies, dates, or projects. Anything uncertain is recorded in ``warnings`` /
``review_notes`` and ``metadata.needs_review`` is always set to ``True``.

A placeholder hook for future AI-based extraction is provided
(:func:`parse_with_ai`). It requires no API key and makes no network calls in
this phase - it simply returns ``None`` so callers fall back to the
deterministic parser.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from app.models.candidate_profile import (
    CandidateProfile,
    Identity,
    Links,
    Metadata,
    Skills,
)
from app.models.resume import ResumeParseResult

# --- Regex patterns -------------------------------------------------------

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Matches common US-style phone formats, optionally with country code.
PHONE_RE = re.compile(
    r"(?:(?:\+?1[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]?)\d{3}[\s.\-]?\d{4})"
)

LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub)/[A-Za-z0-9_\-%/]+",
    re.IGNORECASE,
)

GITHUB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_\-.]+",
    re.IGNORECASE,
)

# --- Skill keywords -------------------------------------------------------

# Canonical skill name -> profile skills category.
SKILL_CATEGORIES: dict[str, str] = {
    # Programming languages
    "Python": "programming_languages",
    "Java": "programming_languages",
    "C#": "programming_languages",
    "C++": "programming_languages",
    "JavaScript": "programming_languages",
    "TypeScript": "programming_languages",
    # Frameworks / libraries
    "React": "frameworks",
    "Node.js": "frameworks",
    "Express": "frameworks",
    "FastAPI": "frameworks",
    "Flask": "frameworks",
    "Django": "frameworks",
    # Databases
    "SQL": "databases",
    "PostgreSQL": "databases",
    "MySQL": "databases",
    "SQLite": "databases",
    "MongoDB": "databases",
    # Cloud
    "AWS": "cloud",
    "Azure": "cloud",
    "GCP": "cloud",
    # Tools
    "Docker": "tools",
    "Git": "tools",
    "GitHub": "tools",
    "Linux": "tools",
    "REST": "tools",
    "GraphQL": "tools",
    "Playwright": "tools",
    "Selenium": "tools",
    # Other markup / data libraries
    "HTML": "other",
    "CSS": "other",
    "pandas": "other",
    "NumPy": "other",
}


def _skill_pattern(keyword: str) -> re.Pattern[str]:
    """Build a case-insensitive, boundary-aware pattern for a skill keyword.

    The custom boundaries treat ``+``, ``#`` and ``.`` as part of a token so
    that ``C++`` and ``C#`` match correctly and ``Java`` does not match inside
    ``JavaScript``.
    """

    return re.compile(
        r"(?<![A-Za-z0-9+#.])" + re.escape(keyword) + r"(?![A-Za-z0-9+#.])",
        re.IGNORECASE,
    )


_SKILL_PATTERNS: dict[str, re.Pattern[str]] = {
    name: _skill_pattern(name) for name in SKILL_CATEGORIES
}


# --- Helpers --------------------------------------------------------------

def _first_match(pattern: re.Pattern[str], text: str) -> Optional[str]:
    match = pattern.search(text)
    return match.group(0) if match else None


def _looks_like_name(line: str) -> bool:
    """Heuristic: does this line look like a person's name?"""

    stripped = line.strip()
    if not stripped or "@" in stripped or any(ch.isdigit() for ch in stripped):
        return False
    if "http" in stripped.lower() or "/" in stripped:
        return False
    words = stripped.split()
    if not (1 < len(words) <= 4):
        return False
    # Each word should be mostly alphabetic (allow hyphen/apostrophe/period).
    for word in words:
        letters = word.replace("-", "").replace("'", "").replace(".", "")
        if not letters.isalpha():
            return False
    return True


def _guess_name(text: str) -> Optional[str]:
    """Guess the candidate's full name from the top few non-empty lines."""

    non_empty = [line.strip() for line in text.splitlines() if line.strip()]
    for line in non_empty[:5]:
        if _looks_like_name(line):
            return line
    return None


def _detect_skills(text: str) -> tuple[Skills, list[str]]:
    """Return detected skills grouped by category, plus a flat list of names."""

    grouped: dict[str, list[str]] = {
        "programming_languages": [],
        "frameworks": [],
        "tools": [],
        "databases": [],
        "cloud": [],
        "other": [],
    }
    flat: list[str] = []
    for name, pattern in _SKILL_PATTERNS.items():
        if pattern.search(text):
            grouped[SKILL_CATEGORIES[name]].append(name)
            flat.append(name)
    return Skills(**grouped), flat


# --- Public API -----------------------------------------------------------

def parse_resume_text_to_profile(
    text: str,
    source_file_name: str,
    source_file_type: str,
) -> ResumeParseResult:
    """Build a rough :class:`CandidateProfile` from extracted resume text.

    Only deterministically detectable fields are populated. Everything else is
    left blank/None/empty and flagged for manual review.
    """

    warnings: list[str] = []
    review_notes: list[str] = []
    missing_fields: list[str] = []

    if not text or not text.strip():
        warnings.append("Resume text was empty; no fields could be extracted.")

    # Contact details.
    email = _first_match(EMAIL_RE, text)
    phone = _first_match(PHONE_RE, text)
    linkedin = _first_match(LINKEDIN_RE, text)
    github = _first_match(GITHUB_RE, text)

    # Name.
    full_name = _guess_name(text)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    if full_name:
        parts = full_name.split()
        first_name = parts[0]
        last_name = parts[-1] if len(parts) > 1 else None
        review_notes.append(
            f"Name '{full_name}' was guessed from the top of the resume; "
            "please verify."
        )
    else:
        warnings.append("Could not confidently determine the candidate's name.")

    # Skills.
    skills, detected_skills = _detect_skills(text)
    if not detected_skills:
        warnings.append("No known skill keywords were detected.")

    identity = Identity(
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        email=email,
        phone=phone,
    )
    links = Links(linkedin=linkedin, github=github)

    # Track which key fields are missing so the UI can prompt for them.
    if not email:
        missing_fields.append("identity.email")
    if not phone:
        missing_fields.append("identity.phone")
    if not full_name:
        missing_fields.append("identity.full_name")
    if not linkedin:
        missing_fields.append("links.linkedin")
    if not github:
        missing_fields.append("links.github")
    if not detected_skills:
        missing_fields.append("skills")
    # Sections the deterministic parser never fills (by design).
    missing_fields.extend(["education", "experience", "projects"])
    review_notes.append(
        "Education, experience, and projects are not auto-extracted in this "
        "phase. Please add them manually."
    )

    metadata = Metadata(
        source_file_name=source_file_name,
        source_file_type=source_file_type,
        extracted_at=datetime.now(timezone.utc),
        needs_review=True,
        review_notes=review_notes,
    )

    profile = CandidateProfile(
        identity=identity,
        links=links,
        skills=skills,
        metadata=metadata,
    )

    confidence = _estimate_confidence(
        has_email=bool(email),
        has_phone=bool(phone),
        has_name=bool(full_name),
        has_links=bool(linkedin or github),
        has_skills=bool(detected_skills),
    )

    return ResumeParseResult(
        raw_text=text,
        profile=profile,
        warnings=warnings,
        missing_fields=missing_fields,
        confidence=confidence,
        source_file_name=source_file_name,
        source_file_type=source_file_type,
    )


def _estimate_confidence(
    *,
    has_email: bool,
    has_phone: bool,
    has_name: bool,
    has_links: bool,
    has_skills: bool,
) -> float:
    """Very rough confidence score in [0.0, 1.0] for the extraction."""

    signals = [has_email, has_phone, has_name, has_links, has_skills]
    return round(sum(1 for s in signals if s) / len(signals), 2)


def parse_with_ai(
    text: str,
    source_file_name: str,
    source_file_type: str,
) -> Optional[ResumeParseResult]:
    """Placeholder for future AI-based structured extraction.

    Intentionally returns ``None`` in this phase: no API key is required and no
    network calls are made. When implemented later, this should call an LLM
    with a structured-output schema and return a :class:`ResumeParseResult`,
    while still flagging sensitive fields for manual review.
    """

    return None
