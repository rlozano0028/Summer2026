"""Tests for the Phase 7 safety policy.

These tests exist to prove the refusals, not the happy path. Each one describes a
way a real value could leak onto a real application page, and asserts that it does
not happen.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.automation import (
    ACTION_FILL,
    ACTION_MANUAL_REVIEW,
    ACTION_SKIP,
    ACTION_SUGGEST,
    FieldMapping,
    FillPlan,
)
from app.models.extension import (
    FIELD_TYPE_CHECKBOX,
    FIELD_TYPE_FILE,
    FIELD_TYPE_RADIO,
    FIELD_TYPE_SUBMIT,
    FIELD_TYPE_TEXT,
    ExtensionDetectedField,
    ExtensionFillInstruction,
)
from app.models.platform import PLATFORM_GREENHOUSE, PLATFORM_LOCAL, PageSafetyDecision
from app.services.platform_allowlist import APPROVED_DOMAINS_ENV_VAR
from app.services.platform_policy import (
    REAL_PAGE_REVIEW_WARNING,
    build_real_platform_warnings,
    downgrade_unsupported_fields,
    enforce_instruction_safety,
    validate_real_platform_request,
)

GREENHOUSE_PAGE = "https://boards.greenhouse.io/acme/jobs/1"
LOCAL_PAGE = "http://127.0.0.1:8000/sample-forms/basic-application.html"


def _field(field_id: str = "f1", **kwargs: object) -> ExtensionDetectedField:
    payload: dict[str, object] = {
        "field_id": field_id,
        "selector": f"#{field_id}",
        "tag_name": "input",
        "input_type": "text",
    }
    payload.update(kwargs)
    return ExtensionDetectedField(**payload)


def _instruction(**kwargs: object) -> ExtensionFillInstruction:
    payload: dict[str, object] = {
        "field_id": "f1",
        "selector": "#f1",
        "action": ACTION_FILL,
        "value": "ada@example.com",
        "field_type": FIELD_TYPE_TEXT,
        "category": "identity.email",
    }
    payload.update(kwargs)
    return ExtensionFillInstruction(**payload)


def _plan(*mappings: FieldMapping) -> FillPlan:
    actions = [mapping.action for mapping in mappings]
    return FillPlan(
        form_name="greenhouse",
        form_url=GREENHOUSE_PAGE,
        generated_at=datetime.now(timezone.utc),
        mappings=list(mappings),
        fill_count=actions.count(ACTION_FILL),
        suggest_count=actions.count(ACTION_SUGGEST),
        manual_review_count=actions.count(ACTION_MANUAL_REVIEW),
        skip_count=actions.count(ACTION_SKIP),
    )


def _mapping(field_id: str, action: str = ACTION_FILL) -> FieldMapping:
    return FieldMapping(
        field_id=field_id,
        selector=f"#{field_id}",
        profile_path="identity.email",
        action=action,
        category="identity.email",
        reason="matched",
    )


# --- validate_real_platform_request -------------------------------------------


def test_real_page_without_confirmation_is_refused() -> None:
    decision = validate_real_platform_request(GREENHOUSE_PAGE, False)
    assert decision.allowed is False
    assert decision.requires_user_confirmation is True
    assert "confirm" in (decision.blocked_reason or "").lower()


def test_real_page_with_confirmation_is_allowed() -> None:
    decision = validate_real_platform_request(GREENHOUSE_PAGE, True)
    assert decision.allowed is True
    assert decision.platform_id == PLATFORM_GREENHOUSE


def test_local_page_needs_no_confirmation() -> None:
    decision = validate_real_platform_request(LOCAL_PAGE, False)
    assert decision.allowed is True
    assert decision.platform_id == PLATFORM_LOCAL
    assert decision.requires_user_confirmation is False


def test_confirmation_cannot_unblock_an_unsupported_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirming does not grant access; it only satisfies a page already allowed."""

    monkeypatch.delenv(APPROVED_DOMAINS_ENV_VAR, raising=False)
    decision = validate_real_platform_request("https://evil.example/apply", True)
    assert decision.allowed is False
    assert decision.blocked_reason


# --- downgrade_unsupported_fields ---------------------------------------------


def test_custom_controls_are_downgraded_to_manual_review() -> None:
    plan = _plan(_mapping("f1"), _mapping("f2"))
    fields = [
        _field("f1"),
        _field("f2", is_custom_control=True, unsupported_reason="ARIA combobox"),
    ]

    updated, count = downgrade_unsupported_fields(plan, fields)

    assert count == 1
    by_id = {mapping.field_id: mapping for mapping in updated.mappings}
    assert by_id["f1"].action == ACTION_FILL
    assert by_id["f2"].action == ACTION_MANUAL_REVIEW
    assert "ARIA combobox" in by_id["f2"].reason
    assert updated.fill_count == 1
    assert updated.manual_review_count == 1


def test_downgrade_does_not_mutate_the_original_plan() -> None:
    plan = _plan(_mapping("f1"))
    downgrade_unsupported_fields(plan, [_field("f1", is_custom_control=True)])
    assert plan.mappings[0].action == ACTION_FILL
    assert plan.fill_count == 1


def test_downgrade_is_a_no_op_without_custom_controls() -> None:
    plan = _plan(_mapping("f1"))
    updated, count = downgrade_unsupported_fields(plan, [_field("f1")])
    assert count == 0
    assert updated is plan


# --- enforce_instruction_safety -----------------------------------------------


@pytest.mark.parametrize("action", [ACTION_SUGGEST, ACTION_MANUAL_REVIEW, ACTION_SKIP])
def test_non_fill_actions_never_carry_a_value(action: str) -> None:
    cleaned, warnings = enforce_instruction_safety([_instruction(action=action)])
    assert cleaned[0].value is None
    assert warnings and action in warnings[0]


@pytest.mark.parametrize(
    "category",
    [
        "sensitive.work_authorization",
        "sensitive.sponsorship",
        "sensitive.salary",
        "sensitive.demographic",
        "sensitive.disability",
        "sensitive.veteran",
        "sensitive.legal_acknowledgment",
        "sensitive.criminal_history",
    ],
)
def test_sensitive_categories_never_carry_a_value(category: str) -> None:
    cleaned, warnings = enforce_instruction_safety([_instruction(category=category)])
    assert cleaned[0].value is None
    assert warnings


@pytest.mark.parametrize(
    "field_type",
    [FIELD_TYPE_FILE, FIELD_TYPE_CHECKBOX, FIELD_TYPE_RADIO, FIELD_TYPE_SUBMIT, "other"],
)
def test_unfillable_field_types_never_carry_a_value(field_type: str) -> None:
    cleaned, _ = enforce_instruction_safety([_instruction(field_type=field_type)])
    assert cleaned[0].value is None


@pytest.mark.parametrize(
    "field_kwargs",
    [
        {"input_type": "password"},
        {"is_file_upload": True},
        {"is_submit_control": True},
        {"is_custom_control": True},
        {"disabled": True},
        {"readonly": True},
        {"visible": False},
    ],
)
def test_unsafe_elements_never_carry_a_value(field_kwargs: dict[str, object]) -> None:
    cleaned, warnings = enforce_instruction_safety(
        [_instruction()], [_field("f1", **field_kwargs)]
    )
    assert cleaned[0].value is None
    assert warnings


def test_safe_text_field_keeps_its_value() -> None:
    cleaned, warnings = enforce_instruction_safety([_instruction()], [_field("f1")])
    assert cleaned[0].value == "ada@example.com"
    assert warnings == []


def test_enforcement_does_not_mutate_its_input() -> None:
    original = _instruction(action=ACTION_SUGGEST)
    enforce_instruction_safety([original])
    assert original.value == "ada@example.com"


def test_withheld_warnings_never_contain_the_value() -> None:
    secret = "super-secret-value"
    cleaned, warnings = enforce_instruction_safety(
        [_instruction(value=secret, action=ACTION_SUGGEST)]
    )
    assert cleaned[0].value is None
    assert all(secret not in warning for warning in warnings)


# --- build_real_platform_warnings ---------------------------------------------


def test_real_page_warnings_include_the_review_reminder() -> None:
    safety = PageSafetyDecision(
        allowed=True,
        platform_id=PLATFORM_GREENHOUSE,
        requires_user_confirmation=True,
        warnings=["Greenhouse note"],
    )
    warnings = build_real_platform_warnings(safety, [_field("f1")], unsupported_count=2)
    assert "Greenhouse note" in warnings
    assert REAL_PAGE_REVIEW_WARNING in warnings
    assert any("custom controls" in warning for warning in warnings)


def test_local_page_warnings_stay_quiet() -> None:
    safety = PageSafetyDecision(allowed=True, platform_id=PLATFORM_LOCAL)
    assert build_real_platform_warnings(safety, [_field("f1")]) == []


def test_empty_field_list_is_explained() -> None:
    safety = PageSafetyDecision(allowed=True, platform_id=PLATFORM_LOCAL)
    warnings = build_real_platform_warnings(safety, [])
    assert any("no fields were detected" in warning.lower() for warning in warnings)


def test_file_uploads_are_called_out() -> None:
    safety = PageSafetyDecision(allowed=True, platform_id=PLATFORM_LOCAL)
    warnings = build_real_platform_warnings(
        safety, [_field("resume", input_type="file", is_file_upload=True)]
    )
    assert any("file upload" in warning.lower() for warning in warnings)


def test_warnings_are_deduplicated() -> None:
    safety = PageSafetyDecision(
        allowed=True,
        platform_id=PLATFORM_GREENHOUSE,
        warnings=[REAL_PAGE_REVIEW_WARNING, REAL_PAGE_REVIEW_WARNING],
    )
    warnings = build_real_platform_warnings(safety, [_field("f1")])
    assert warnings.count(REAL_PAGE_REVIEW_WARNING) == 1
