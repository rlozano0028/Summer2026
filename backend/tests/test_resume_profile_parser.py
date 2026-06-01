"""Tests for the Phase 2 deterministic resume parser."""

from __future__ import annotations

from app.services.resume_profile_parser import parse_resume_text_to_profile

SAMPLE_RESUME = """\
Jane Doe
jane.doe@example.com
(555) 123-4567
https://linkedin.com/in/janedoe
https://github.com/janedoe

Skills: Python, FastAPI, PostgreSQL, Docker, React, TypeScript
"""


def _parse(text: str):
    return parse_resume_text_to_profile(
        text=text, source_file_name="resume.txt", source_file_type="txt"
    )


def test_email_detection() -> None:
    result = _parse(SAMPLE_RESUME)
    assert result.profile.identity.email == "jane.doe@example.com"


def test_github_and_linkedin_detection() -> None:
    result = _parse(SAMPLE_RESUME)
    assert result.profile.links.github == "https://github.com/janedoe"
    assert result.profile.links.linkedin == "https://linkedin.com/in/janedoe"


def test_skill_keyword_detection() -> None:
    result = _parse(SAMPLE_RESUME)
    skills = result.profile.skills

    assert "Python" in skills.programming_languages
    assert "TypeScript" in skills.programming_languages
    assert "FastAPI" in skills.frameworks
    assert "React" in skills.frameworks
    assert "PostgreSQL" in skills.databases
    assert "Docker" in skills.tools


def test_java_does_not_match_inside_javascript() -> None:
    """Boundary handling: 'JavaScript' must not register plain 'Java'."""

    result = _parse("Experienced with JavaScript only.")
    assert "Java" not in result.profile.skills.programming_languages
    assert "JavaScript" in result.profile.skills.programming_languages


def test_empty_text_returns_warnings_and_needs_review() -> None:
    result = _parse("")

    assert result.profile.metadata.needs_review is True
    assert result.warnings  # non-empty
    assert result.confidence == 0.0
    # Sections that are never auto-filled are reported as missing.
    assert "education" in result.missing_fields
    assert "experience" in result.missing_fields


def test_parser_always_sets_needs_review() -> None:
    result = _parse(SAMPLE_RESUME)
    assert result.profile.metadata.needs_review is True
    # Deterministic parser never invents these sections.
    assert result.profile.education == []
    assert result.profile.experience == []
    assert result.profile.projects == []
