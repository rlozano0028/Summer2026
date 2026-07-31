"""Phase 6 safety tests: what the extension endpoint must never hand back.

Every test here asserts a privacy or safety invariant end-to-end through the API,
so a future refactor of the mapping engine cannot quietly start leaking values to
the extension. No Chrome, no extension, no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.candidate_profile import CandidateProfile, Identity, Links
from app.services import field_mapping_overrides, profile_storage

LOCAL_PAGE = "http://127.0.0.1:8000/sample-forms/basic-application.html"

# Real values stored in the temp profile; none of them may appear in a response
# except as the ``value`` of a safe action="fill" instruction.
EMAIL = "ada@example.com"
PHONE = "555-000-1234"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv(profile_storage.STORAGE_PATH_ENV_VAR, str(tmp_path / "profile.json"))
    monkeypatch.setenv(
        field_mapping_overrides.OVERRIDES_DIR_ENV_VAR, str(tmp_path / "overrides")
    )
    client = TestClient(app)
    profile = CandidateProfile(
        identity=Identity(
            first_name="Ada",
            last_name="Lovelace",
            email=EMAIL,
            phone=PHONE,
            city="London",
        ),
        links=Links(github="https://github.com/ada"),
    )
    assert client.put("/profile", json=profile.model_dump(mode="json")).status_code == 200
    return client


def _field(field_id: str, **kwargs: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "field_id": field_id,
        "selector": f"#{field_id}",
        "tag_name": "input",
        "input_type": "text",
    }
    payload.update(kwargs)
    return payload


def _analyze(client: TestClient, fields: list[dict[str, object]]) -> dict[str, object]:
    response = client.post(
        "/extension/analyze-page",
        json={
            "page_url": LOCAL_PAGE,
            "page_title": "Basic Application",
            "form_name": "basic",
            "fields": fields,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _instructions_by_id(body: dict[str, object]) -> dict[str, dict[str, object]]:
    return {i["field_id"]: i for i in body["instructions"]}  # type: ignore[index,union-attr]


def test_only_fill_actions_carry_values(client: TestClient) -> None:
    """Across a mixed form, value is non-None if and only if action == fill."""

    fields = [
        _field("f_first", selector="#first_name", name="first_name", label_text="First name"),
        _field("f_email", selector="#email", input_type="email", name="email", label_text="Email"),
        _field(
            "f_essay",
            selector="#why",
            tag_name="textarea",
            input_type=None,
            is_textarea=True,
            label_text="Why do you want this job?",
        ),
        _field(
            "f_resume",
            selector="#resume",
            input_type="file",
            name="resume",
            label_text="Upload resume",
            is_file_upload=True,
        ),
        _field(
            "f_salary",
            selector="#salary",
            name="desired_salary",
            label_text="Desired salary expectations",
        ),
        _field(
            "f_submit",
            selector="button[type=submit]",
            tag_name="button",
            input_type="submit",
            is_submit_control=True,
        ),
    ]
    body = _analyze(client, fields)
    instructions = _instructions_by_id(body)

    for instruction in instructions.values():
        if instruction["action"] == "fill":
            assert instruction["value"], f"fill instruction missing value: {instruction}"
        else:
            assert instruction["value"] is None, f"non-fill leaked a value: {instruction}"


def test_manual_review_fields_never_receive_values(client: TestClient) -> None:
    fields = [
        _field(
            "f_essay",
            tag_name="textarea",
            input_type=None,
            is_textarea=True,
            label_text="Tell us about yourself",
        ),
        _field("f_mystery", name="q_1234", label_text="Question 1234"),
    ]
    body = _analyze(client, fields)

    for instruction in body["instructions"]:  # type: ignore[union-attr]
        assert instruction["action"] == "manual_review"
        assert instruction["value"] is None


def test_sensitive_fields_never_receive_values(client: TestClient) -> None:
    fields = [
        _field("f_auth", name="work_authorization", label_text="Are you authorized to work?"),
        _field("f_sponsor", name="sponsorship", label_text="Will you require visa sponsorship?"),
        _field("f_salary", name="salary", label_text="Desired salary"),
        _field("f_gender", name="gender", label_text="Gender"),
        _field("f_veteran", name="veteran_status", label_text="Veteran status"),
        _field("f_disability", name="disability", label_text="Disability status"),
        _field("f_criminal", name="criminal_history", label_text="Criminal history"),
    ]
    body = _analyze(client, fields)
    plan_by_id = {m["field_id"]: m for m in body["fill_plan"]["mappings"]}  # type: ignore[index]

    assert body["fill_plan"]["fill_count"] == 0  # type: ignore[index]
    assert any(m["sensitive"] for m in plan_by_id.values())
    for instruction in body["instructions"]:  # type: ignore[union-attr]
        assert instruction["action"] != "fill"
        assert instruction["value"] is None


def test_password_fields_are_dropped_and_reported(client: TestClient) -> None:
    fields = [
        _field("f_email", input_type="email", name="email", label_text="Email"),
        _field("f_pw", input_type="password", name="password", label_text="Password"),
    ]
    body = _analyze(client, fields)

    plan_ids = {m["field_id"] for m in body["fill_plan"]["mappings"]}  # type: ignore[index]
    instruction_ids = {i["field_id"] for i in body["instructions"]}  # type: ignore[union-attr]
    assert "f_pw" not in plan_ids
    assert "f_pw" not in instruction_ids
    assert any("password" in w.lower() for w in body["warnings"])  # type: ignore[union-attr]


def test_submit_controls_are_skipped(client: TestClient) -> None:
    fields = [
        _field("f_email", input_type="email", name="email", label_text="Email"),
        _field(
            "f_submit",
            selector="button[type=submit]",
            tag_name="button",
            input_type="submit",
            is_submit_control=True,
        ),
    ]
    body = _analyze(client, fields)
    instructions = _instructions_by_id(body)

    assert instructions["f_submit"]["action"] == "skip"
    assert instructions["f_submit"]["value"] is None


def test_file_uploads_are_manual_review_without_values(client: TestClient) -> None:
    fields = [
        _field(
            "f_resume",
            input_type="file",
            name="resume",
            label_text="Resume / CV",
            is_file_upload=True,
        )
    ]
    body = _analyze(client, fields)
    instruction = body["instructions"][0]  # type: ignore[index]

    assert instruction["action"] == "manual_review"
    assert instruction["value"] is None
    assert instruction["field_type"] == "file"


def test_plan_previews_are_redacted_not_raw(client: TestClient) -> None:
    """The fill_plan half of the response must never contain a raw value."""

    fields = [
        _field("f_email", input_type="email", name="email", label_text="Email"),
        _field("f_phone", input_type="tel", name="phone", label_text="Phone number"),
    ]
    body = _analyze(client, fields)

    for mapping in body["fill_plan"]["mappings"]:  # type: ignore[index]
        assert mapping["value_preview"] not in (EMAIL, PHONE)


def test_disabled_and_readonly_fields_get_no_values(client: TestClient) -> None:
    fields = [
        _field("f_disabled", input_type="email", name="email", label_text="Email", disabled=True),
        _field("f_readonly", input_type="email", name="email", label_text="Email", readonly=True),
        _field("f_hidden", input_type="email", name="email", label_text="Email", visible=False),
    ]
    body = _analyze(client, fields)

    for instruction in body["instructions"]:  # type: ignore[union-attr]
        assert instruction["action"] == "skip"
        assert instruction["value"] is None


def test_analyze_page_writes_nothing_to_disk(client: TestClient, tmp_path: Path) -> None:
    """An extension analysis creates no report, override, or cache file."""

    before = sorted(p.name for p in tmp_path.rglob("*") if p.is_file())
    _analyze(client, [_field("f_email", input_type="email", name="email", label_text="Email")])
    after = sorted(p.name for p in tmp_path.rglob("*") if p.is_file())

    # Only the profile saved by the fixture exists; analysis added nothing.
    assert before == after == ["profile.json"]
