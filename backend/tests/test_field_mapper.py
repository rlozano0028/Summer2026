"""Tests for the deterministic field mapper (Phase 4)."""

from __future__ import annotations

from app.models.automation import (
    ACTION_FILL,
    ACTION_MANUAL_REVIEW,
    ACTION_SKIP,
    FormField,
)
from app.models.candidate_profile import (
    CandidateProfile,
    Identity,
    Links,
    Skills,
)
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
