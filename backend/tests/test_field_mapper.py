"""Tests for the deterministic field mapper (Phase 4 + Phase 5)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.automation import (
    ACTION_FILL,
    ACTION_MANUAL_REVIEW,
    ACTION_SKIP,
    ACTION_SUGGEST,
    FormField,
)
from app.models.candidate_profile import (
    CandidateProfile,
    Identity,
    Links,
    Skills,
)
from app.models.field_mapping import FieldCategory, MappingOverride
from app.services.field_mapper import build_fill_plan, map_field_to_profile


def _profile() -> CandidateProfile:
    return CandidateProfile(
        identity=Identity(
            first_name="Ada",
            last_name="Lovelace",
            full_name="Ada Lovelace",
            email="ada@example.com",
            phone="555-123-4567",
            city="London",
            state="LDN",
            country="UK",
        ),
        links=Links(
            linkedin="https://linkedin.com/in/ada",
            github="https://github.com/ada",
            portfolio="https://ada.dev",
        ),
        skills=Skills(
            programming_languages=["Python", "Rust"],
            frameworks=["FastAPI"],
            tools=["Git"],
            databases=["Postgres"],
            cloud=["AWS"],
        ),
    )


def _field(**kwargs) -> FormField:
    defaults = dict(field_id="f0", selector="#f0", tag_name="input", input_type="text")
    defaults.update(kwargs)
    return FormField(**defaults)


def test_maps_first_name() -> None:
    field = _field(name="first_name", id_attribute="first_name", label_text="First name")
    mapping = map_field_to_profile(field, _profile())
    assert mapping.action == ACTION_FILL
    assert mapping.profile_path == "identity.first_name"
    assert mapping.confidence >= 0.90


def test_maps_email() -> None:
    field = _field(name="email", input_type="email", label_text="Email address")
    mapping = map_field_to_profile(field, _profile())
    assert mapping.action == ACTION_FILL
    assert mapping.profile_path == "identity.email"
    # Preview must be redacted, never the full address.
    assert mapping.value_preview is not None
    assert mapping.value_preview != "ada@example.com"


def test_maps_linkedin_and_github() -> None:
    linkedin = map_field_to_profile(_field(name="linkedin", label_text="LinkedIn"), _profile())
    github = map_field_to_profile(_field(name="github", label_text="GitHub"), _profile())
    assert linkedin.action == ACTION_FILL
    assert linkedin.profile_path == "links.linkedin"
    assert github.action == ACTION_FILL
    assert github.profile_path == "links.github"


def test_maps_skills() -> None:
    field = _field(name="skills", label_text="Skills")
    mapping = map_field_to_profile(field, _profile())
    assert mapping.action == ACTION_FILL
    assert mapping.profile_path == "skills"


def test_resume_upload_is_manual_review_without_file() -> None:
    field = _field(
        name="resume",
        tag_name="input",
        input_type="file",
        is_file_upload=True,
        label_text="Resume / CV",
    )
    mapping = map_field_to_profile(field, _profile())
    assert mapping.action == ACTION_MANUAL_REVIEW
    assert mapping.sensitive is False


def test_work_authorization_is_sensitive_manual_review() -> None:
    field = _field(
        name="work_authorization",
        tag_name="select",
        input_type=None,
        label_text="Are you legally authorized to work?",
        options=["yes", "no"],
    )
    mapping = map_field_to_profile(field, _profile())
    assert mapping.action == ACTION_MANUAL_REVIEW
    assert mapping.sensitive is True


def test_sponsorship_is_sensitive_manual_review() -> None:
    field = _field(
        name="sponsorship",
        tag_name="select",
        input_type=None,
        label_text="Will you require visa sponsorship?",
        options=["yes", "no"],
    )
    mapping = map_field_to_profile(field, _profile())
    assert mapping.action == ACTION_MANUAL_REVIEW
    assert mapping.sensitive is True


def test_salary_expectation_is_sensitive_manual_review() -> None:
    field = _field(name="salary_expectation", label_text="Salary expectation")
    mapping = map_field_to_profile(field, _profile())
    assert mapping.action == ACTION_MANUAL_REVIEW
    assert mapping.sensitive is True


def test_submit_button_is_skipped() -> None:
    field = _field(
        field_id="submit",
        selector="#submit",
        tag_name="button",
        input_type="submit",
        is_submit_control=True,
        label_text="Submit",
    )
    mapping = map_field_to_profile(field, _profile())
    assert mapping.action == ACTION_SKIP


def test_fill_plan_counts_are_correct() -> None:
    fields = [
        _field(field_id="a", name="first_name", label_text="First name"),
        _field(field_id="b", name="email", input_type="email", label_text="Email"),
        _field(
            field_id="c",
            name="work_authorization",
            tag_name="select",
            input_type=None,
            label_text="Work authorization",
            options=["yes", "no"],
        ),
        _field(
            field_id="d",
            name="resume",
            input_type="file",
            is_file_upload=True,
            label_text="Resume",
        ),
        _field(field_id="e", name="mystery_field", label_text="Mystery"),
        _field(
            field_id="f",
            selector="#submit",
            tag_name="button",
            input_type="submit",
            is_submit_control=True,
            label_text="Submit",
        ),
    ]
    plan = build_fill_plan("basic", "file:///tmp/basic.html", fields, _profile())
    assert plan.fill_count == 2
    assert plan.manual_review_count == 3
    assert plan.skip_count == 1
    assert plan.suggest_count == 0
    total = (
        plan.fill_count
        + plan.suggest_count
        + plan.manual_review_count
        + plan.skip_count
    )
    assert total == len(fields)


# --- Phase 5 additions ------------------------------------------------------


def _override(**kwargs) -> MappingOverride:
    now = datetime.now(timezone.utc)
    defaults = dict(
        override_id="ov1",
        form_name="basic",
        field_fingerprint="fp",
        category=FieldCategory.IDENTITY_FIRST_NAME.value,
        profile_path="identity.first_name",
        action=ACTION_FILL,
        note=None,
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return MappingOverride(**defaults)


def test_maps_last_name_high_confidence() -> None:
    mapping = map_field_to_profile(_field(name="last_name", label_text="Last name"), _profile())
    assert mapping.action == ACTION_FILL
    assert mapping.category == FieldCategory.IDENTITY_LAST_NAME.value
    assert mapping.confidence >= 0.90


def test_maps_phone_high_confidence() -> None:
    mapping = map_field_to_profile(_field(name="phone", input_type="tel", label_text="Phone number"), _profile())
    assert mapping.action == ACTION_FILL
    assert mapping.category == FieldCategory.IDENTITY_PHONE.value


def test_autocomplete_token_maps_first_name() -> None:
    mapping = map_field_to_profile(_field(name="fn", autocomplete="given-name"), _profile())
    assert mapping.category == FieldCategory.IDENTITY_FIRST_NAME.value
    assert mapping.action == ACTION_FILL


def test_classification_carries_evidence() -> None:
    mapping = map_field_to_profile(_field(name="email", label_text="Email"), _profile())
    assert mapping.evidence
    assert any(ev.source in {"label", "name"} for ev in mapping.evidence)


def test_website_is_suggest_not_fill() -> None:
    mapping = map_field_to_profile(_field(name="website", label_text="Website"), _profile())
    assert mapping.category == FieldCategory.LINKS_PORTFOLIO.value
    assert mapping.action == ACTION_SUGGEST


def test_cover_letter_is_manual_review() -> None:
    field = _field(name="cover_letter", tag_name="textarea", input_type=None, label_text="Cover letter")
    mapping = map_field_to_profile(field, _profile())
    assert mapping.action == ACTION_MANUAL_REVIEW
    assert mapping.category == FieldCategory.CUSTOM_COVER_LETTER.value


def test_disabled_readonly_hidden_are_skipped() -> None:
    disabled = map_field_to_profile(_field(name="first_name", disabled=True), _profile())
    readonly = map_field_to_profile(_field(name="first_name", readonly=True), _profile())
    hidden = map_field_to_profile(_field(name="csrf", input_type="hidden"), _profile())
    assert disabled.action == ACTION_SKIP
    assert readonly.action == ACTION_SKIP
    assert hidden.action == ACTION_SKIP


def test_checkbox_is_manual_review() -> None:
    field = _field(name="newsletter", input_type="checkbox", label_text="Subscribe")
    mapping = map_field_to_profile(field, _profile())
    assert mapping.action == ACTION_MANUAL_REVIEW


def test_override_can_force_skip() -> None:
    field = _field(name="first_name", label_text="First name")
    mapping = map_field_to_profile(field, _profile(), override=_override(action=ACTION_SKIP))
    assert mapping.action == ACTION_SKIP


def test_override_cannot_force_fill_sensitive_field() -> None:
    field = _field(name="salary_expectation", label_text="Desired salary")
    override = _override(
        category=FieldCategory.SENSITIVE_SALARY.value,
        profile_path=None,
        action=ACTION_FILL,
    )
    mapping = map_field_to_profile(field, _profile(), override=override)
    assert mapping.action == ACTION_MANUAL_REVIEW
    assert mapping.sensitive is True
    assert mapping.warnings  # warns that the unsafe override was downgraded
