"""Tests for the Phase 5 profile value resolver."""

from __future__ import annotations

from app.models.candidate_profile import CandidateProfile, Identity, Links, Skills
from app.models.field_mapping import FieldCategory
from app.services.field_value_resolver import resolve_profile_value, resolve_raw_value


def _profile() -> CandidateProfile:
    return CandidateProfile(
        identity=Identity(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            phone="555-123-4567",
            city="London",
        ),
        links=Links(linkedin="https://linkedin.com/in/ada", github="https://github.com/ada"),
        skills=Skills(programming_languages=["Python", "Rust"], frameworks=["FastAPI"]),
    )


def test_resolves_identity_first_name() -> None:
    res = resolve_profile_value(_profile(), FieldCategory.IDENTITY_FIRST_NAME.value)
    assert res.value_exists is True
    assert res.profile_path == "identity.first_name"
    assert res.value_preview == "Ada"


def test_resolves_links() -> None:
    res = resolve_profile_value(_profile(), FieldCategory.LINKS_LINKEDIN.value)
    assert res.value_exists is True
    assert res.profile_path == "links.linkedin"


def test_resolves_skills() -> None:
    res = resolve_profile_value(_profile(), FieldCategory.SKILLS_PROGRAMMING_LANGUAGES.value)
    assert res.value_exists is True
    combined = resolve_profile_value(_profile(), FieldCategory.SKILLS_COMBINED.value)
    assert combined.value_exists is True


def test_redacts_email_and_phone_previews() -> None:
    email = resolve_profile_value(_profile(), FieldCategory.IDENTITY_EMAIL.value)
    assert email.value_preview != "ada@example.com"
    assert email.value_preview.endswith("@example.com")
    assert email.redacted is True
    phone = resolve_profile_value(_profile(), FieldCategory.IDENTITY_PHONE.value)
    assert phone.value_preview != "555-123-4567"
    assert phone.redacted is True


def test_missing_value_returns_missing_reason() -> None:
    res = resolve_profile_value(_profile(), FieldCategory.IDENTITY_COUNTRY.value)
    assert res.value_exists is False
    assert res.missing_reason


def test_does_not_resolve_sensitive_or_custom() -> None:
    for category in (
        FieldCategory.SENSITIVE_SALARY.value,
        FieldCategory.SENSITIVE_WORK_AUTHORIZATION.value,
        FieldCategory.CUSTOM_COVER_LETTER.value,
        FieldCategory.CUSTOM_SHORT_ANSWER.value,
        FieldCategory.RESUME_FILE.value,
    ):
        res = resolve_profile_value(_profile(), category)
        assert res.value_exists is False


def test_resolve_raw_value_returns_full_value_for_runner() -> None:
    # The runner needs the un-redacted value; reports never store it.
    assert resolve_raw_value(_profile(), "identity.email") == "ada@example.com"
