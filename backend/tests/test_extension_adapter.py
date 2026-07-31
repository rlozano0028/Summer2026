"""Tests for the Phase 6 extension field adapter.

These are pure unit tests: no Chrome, no network, no browser, no disk writes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.automation import (
    ACTION_FILL,
    ACTION_MANUAL_REVIEW,
    ACTION_SKIP,
    ACTION_SUGGEST,
    FieldMapping,
    FillPlan,
)
from app.models.candidate_profile import CandidateProfile, Identity
from app.models.extension import (
    FIELD_TYPE_FILE,
    FIELD_TYPE_SELECT,
    FIELD_TYPE_TEXT,
    FIELD_TYPE_TEXTAREA,
    ExtensionDetectedField,
)
from app.models.field_mapping import FieldCategory
from app.services.extension_field_adapter import (
    build_extension_response,
    convert_extension_fields_to_form_fields,
)


def _field(field_id: str, **kwargs: object) -> ExtensionDetectedField:
    defaults: dict[str, object] = {
        "field_id": field_id,
        "selector": f"#{field_id}",
        "tag_name": "input",
        "input_type": "text",
    }
    defaults.update(kwargs)
    return ExtensionDetectedField(**defaults)  # type: ignore[arg-type]


def _profile() -> CandidateProfile:
    return CandidateProfile(
        identity=Identity(first_name="Ada", last_name="Lovelace", email="ada@example.com")
    )


def _plan(mappings: list[FieldMapping]) -> FillPlan:
    return FillPlan(
        form_name="extension-page",
        form_url="http://127.0.0.1:8000/sample-forms/basic-application.html",
        generated_at=datetime.now(timezone.utc),
        mappings=mappings,
    )


def test_detected_field_serializes_with_defaults() -> None:
    field = ExtensionDetectedField(field_id="f1", selector="#email", tag_name="input")
    data = field.model_dump()
    assert data["field_id"] == "f1"
    assert data["options"] == []
    assert data["visible"] is True
    assert data["is_checkbox"] is False
    # Round-trips through JSON without loss.
    assert ExtensionDetectedField.model_validate_json(field.model_dump_json()) == field


def test_converts_extension_fields_into_form_fields() -> None:
    fields = [
        _field(
            "f1",
            selector="#first_name",
            name="first_name",
            label_text="First name",
            autocomplete="given-name",
            required=True,
        ),
        _field("f2", tag_name="select", is_select=True, options=["Yes", "No"]),
    ]
    converted, dropped = convert_extension_fields_to_form_fields(fields)

    assert dropped == []
    assert [f.field_id for f in converted] == ["f1", "f2"]
    assert converted[0].label_text == "First name"
    assert converted[0].autocomplete == "given-name"
    assert converted[0].required is True
    assert converted[1].is_select is True
    assert converted[1].options == ["Yes", "No"]


def test_password_fields_are_dropped_before_mapping() -> None:
    fields = [
        _field("f1", name="email"),
        _field("f2", input_type="password", name="password"),
        _field("f3", input_type="PASSWORD", name="confirm"),
    ]
    converted, dropped = convert_extension_fields_to_form_fields(fields)

    assert [f.field_id for f in converted] == ["f1"]
    assert dropped == ["f2", "f3"]


def test_fill_action_carries_real_value() -> None:
    fields = [_field("f1", name="email")]
    plan = _plan(
        [
            FieldMapping(
                field_id="f1",
                selector="#f1",
                category=FieldCategory.IDENTITY_EMAIL.value,
                profile_path="identity.email",
                value_preview="a***@example.com",
                action=ACTION_FILL,
                confidence=0.95,
            )
        ]
    )
    response = build_extension_response(
        page_url="http://127.0.0.1:8000/sample-forms/basic-application.html",
        page_title="Basic",
        fill_plan=plan,
        profile=_profile(),
        fields=fields,
    )

    instruction = response.instructions[0]
    assert instruction.value == "ada@example.com"
    assert instruction.value_preview == "a***@example.com"
    assert instruction.field_type == FIELD_TYPE_TEXT


def test_non_fill_actions_never_carry_a_value() -> None:
    fields = [_field(f"f{i}") for i in range(1, 4)]
    plan = _plan(
        [
            FieldMapping(
                field_id="f1",
                selector="#f1",
                category=FieldCategory.LINKS_PORTFOLIO.value,
                profile_path="links.portfolio",
                action=ACTION_SUGGEST,
            ),
            FieldMapping(
                field_id="f2",
                selector="#f2",
                category=FieldCategory.IDENTITY_EMAIL.value,
                profile_path="identity.email",
                action=ACTION_MANUAL_REVIEW,
            ),
            FieldMapping(
                field_id="f3",
                selector="#f3",
                category=FieldCategory.IDENTITY_EMAIL.value,
                profile_path="identity.email",
                action=ACTION_SKIP,
            ),
        ]
    )
    response = build_extension_response(
        page_url="http://127.0.0.1:8000/x.html",
        page_title=None,
        fill_plan=plan,
        profile=_profile(),
        fields=fields,
    )

    assert [i.action for i in response.instructions] == [
        ACTION_SUGGEST,
        ACTION_MANUAL_REVIEW,
        ACTION_SKIP,
    ]
    assert all(i.value is None for i in response.instructions)


def test_sensitive_and_missing_and_upload_never_carry_a_value() -> None:
    fields = [
        _field("f1"),
        _field("f2"),
        _field("f3", input_type="file", is_file_upload=True),
        _field("f4", disabled=True),
    ]
    plan = _plan(
        [
            # Flagged sensitive, even though the action was forced to fill.
            FieldMapping(
                field_id="f1",
                selector="#f1",
                category=FieldCategory.SENSITIVE_SALARY.value,
                profile_path="identity.email",
                action=ACTION_FILL,
                sensitive=True,
            ),
            # Missing value.
            FieldMapping(
                field_id="f2",
                selector="#f2",
                category=FieldCategory.IDENTITY_PHONE.value,
                profile_path="identity.phone",
                action=ACTION_FILL,
                missing_value=True,
            ),
            # File upload.
            FieldMapping(
                field_id="f3",
                selector="#f3",
                category=FieldCategory.RESUME_FILE.value,
                profile_path="identity.email",
                action=ACTION_FILL,
            ),
            # Disabled element.
            FieldMapping(
                field_id="f4",
                selector="#f4",
                category=FieldCategory.IDENTITY_EMAIL.value,
                profile_path="identity.email",
                action=ACTION_FILL,
            ),
        ]
    )
    response = build_extension_response(
        page_url="http://127.0.0.1:8000/x.html",
        page_title=None,
        fill_plan=plan,
        profile=_profile(),
        fields=fields,
    )

    assert all(i.value is None for i in response.instructions)
    assert response.instructions[2].field_type == FIELD_TYPE_FILE


def test_checkbox_and_radio_are_never_given_a_value() -> None:
    fields = [
        _field("f1", input_type="checkbox", is_checkbox=True),
        _field("f2", input_type="radio", is_radio=True),
    ]
    plan = _plan(
        [
            FieldMapping(
                field_id="f1",
                selector="#f1",
                category=FieldCategory.IDENTITY_COUNTRY.value,
                profile_path="identity.country",
                action=ACTION_FILL,
            ),
            FieldMapping(
                field_id="f2",
                selector="#f2",
                category=FieldCategory.IDENTITY_COUNTRY.value,
                profile_path="identity.country",
                action=ACTION_FILL,
            ),
        ]
    )
    response = build_extension_response(
        page_url="http://127.0.0.1:8000/x.html",
        page_title=None,
        fill_plan=plan,
        profile=_profile(),
        fields=fields,
    )

    assert all(i.value is None for i in response.instructions)


def test_field_type_reflects_element_kind() -> None:
    fields = [
        _field("f1", tag_name="textarea", is_textarea=True),
        _field("f2", tag_name="select", is_select=True, options=["Ada"]),
    ]
    plan = _plan(
        [
            FieldMapping(field_id="f1", selector="#f1", action=ACTION_MANUAL_REVIEW),
            FieldMapping(field_id="f2", selector="#f2", action=ACTION_MANUAL_REVIEW),
        ]
    )
    response = build_extension_response(
        page_url="http://127.0.0.1:8000/x.html",
        page_title=None,
        fill_plan=plan,
        profile=_profile(),
        fields=fields,
    )

    assert response.instructions[0].field_type == FIELD_TYPE_TEXTAREA
    assert response.instructions[1].field_type == FIELD_TYPE_SELECT


def test_review_status_is_reported_and_warnings_pass_through() -> None:
    profile = _profile()
    profile.metadata.needs_review = True
    response = build_extension_response(
        page_url="http://127.0.0.1:8000/x.html",
        page_title="X",
        fill_plan=_plan([]),
        profile=profile,
        fields=[],
        warnings=["check me"],
    )

    assert response.profile_review_status is True
    assert response.warnings == ["check me"]
    assert response.instructions == []
