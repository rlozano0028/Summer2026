"""Tests that the Phase 4 automation models serialize/round-trip correctly."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.automation import (
    ACTION_FILL,
    AutofillResult,
    AutomationRequest,
    FieldMapping,
    FillPlan,
    FormField,
)


def test_form_field_defaults() -> None:
    field = FormField(field_id="f0", selector="#email", tag_name="input")
    assert field.required is False
    assert field.visible is True
    assert field.options == []
    assert field.is_file_upload is False


def test_field_mapping_round_trip() -> None:
    mapping = FieldMapping(
        field_id="f0",
        selector="#email",
        profile_path="identity.email",
        value_preview="a***@example.com",
        confidence=0.95,
        action=ACTION_FILL,
        reason="match",
    )
    dumped = mapping.model_dump_json()
    restored = FieldMapping.model_validate_json(dumped)
    assert restored == mapping
    assert restored.action == ACTION_FILL


def test_fill_plan_serializes() -> None:
    plan = FillPlan(
        form_name="basic",
        form_url="file:///tmp/basic.html",
        generated_at=datetime.now(timezone.utc),
        mappings=[],
        fill_count=1,
        suggest_count=2,
        manual_review_count=3,
        skip_count=4,
    )
    data = plan.model_dump(mode="json")
    assert data["fill_count"] == 1
    assert data["skip_count"] == 4
    assert isinstance(data["generated_at"], str)


def test_autofill_result_round_trip() -> None:
    result = AutofillResult(
        form_name="basic",
        form_url="file:///tmp/basic.html",
        started_at=datetime.now(timezone.utc),
        filled_fields=["First name"],
        success=True,
    )
    restored = AutofillResult.model_validate_json(result.model_dump_json())
    assert restored.filled_fields == ["First name"]
    assert restored.success is True


def test_automation_request_defaults() -> None:
    request = AutomationRequest(form_name="basic")
    assert request.headless is False
    assert request.dry_run is False
    assert request.resume_file_path is None
    assert request.keep_browser_open is False
