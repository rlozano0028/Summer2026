"""Tests for the Phase 7 routes: /platforms/* and /extension/analyze-real-page.

Profile storage and the mapping-override store are redirected to temp paths, so no
real personal data is read or written. No browser is opened, no URL is fetched, and
no real job site is contacted: every "real" URL here is only ever a string.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.candidate_profile import CandidateProfile, Identity, Links
from app.models.platform import (
    PLATFORM_GENERIC,
    PLATFORM_GREENHOUSE,
    PLATFORM_LOCAL,
    PLATFORM_UNSUPPORTED,
)
from app.services import field_mapping_overrides, profile_storage
from app.services.platform_allowlist import APPROVED_DOMAINS_ENV_VAR

GREENHOUSE_PAGE = "https://boards.greenhouse.io/acme/jobs/1"
LOCAL_PAGE = "http://127.0.0.1:8000/sample-forms/basic-application.html"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv(profile_storage.STORAGE_PATH_ENV_VAR, str(tmp_path / "profile.json"))
    monkeypatch.setenv(
        field_mapping_overrides.OVERRIDES_DIR_ENV_VAR, str(tmp_path / "overrides")
    )
    monkeypatch.delenv(APPROVED_DOMAINS_ENV_VAR, raising=False)
    return TestClient(app)


def _save_profile(client: TestClient, *, needs_review: bool = False) -> None:
    profile = CandidateProfile(
        identity=Identity(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            phone="555-000-1234",
        ),
        links=Links(github="https://github.com/ada"),
    )
    profile.metadata.needs_review = needs_review
    assert client.put("/profile", json=profile.model_dump(mode="json")).status_code == 200


def _field(field_id: str, **kwargs: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "field_id": field_id,
        "selector": f"#{field_id}",
        "tag_name": "input",
        "input_type": "text",
    }
    payload.update(kwargs)
    return payload


def _contact_fields() -> list[dict[str, object]]:
    return [
        _field("first_name", label_text="First name", name="first_name"),
        _field("last_name", label_text="Last name", name="last_name"),
        _field("email", label_text="Email", name="email", input_type="email"),
    ]


def _analyze_real(
    client: TestClient, fields: list[dict[str, object]], **kwargs: object
) -> object:
    body: dict[str, object] = {
        "page_url": GREENHOUSE_PAGE,
        "page_title": "Acme - Software Engineer",
        "platform_id": PLATFORM_GREENHOUSE,
        "platform_confidence": 0.95,
        "user_confirmed_real_page": True,
        "fields": fields,
    }
    body.update(kwargs)
    return client.post("/extension/analyze-real-page", json=body)


# --- GET /platforms/supported -------------------------------------------------


def test_supported_platforms_lists_platforms_and_domains(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(APPROVED_DOMAINS_ENV_VAR, "careers.acme-corp.example")
    body = client.get("/platforms/supported").json()
    ids = [platform["platform_id"] for platform in body["platforms"]]
    assert PLATFORM_LOCAL in ids
    assert PLATFORM_GREENHOUSE in ids
    assert body["extra_approved_domains"] == ["careers.acme-corp.example"]


# --- POST /platforms/check-url ------------------------------------------------


def test_check_url_reports_a_supported_platform(client: TestClient) -> None:
    body = client.post("/platforms/check-url", json={"page_url": GREENHOUSE_PAGE}).json()
    assert body["detection"]["platform_id"] == PLATFORM_GREENHOUSE
    assert body["safety"]["allowed"] is True
    assert body["safety"]["requires_user_confirmation"] is True


def test_check_url_blocks_an_unsupported_page(client: TestClient) -> None:
    body = client.post(
        "/platforms/check-url", json={"page_url": "https://evil.example/apply"}
    ).json()
    assert body["detection"]["platform_id"] == PLATFORM_UNSUPPORTED
    assert body["safety"]["allowed"] is False
    assert body["safety"]["blocked_reason"]


def test_check_url_blocks_a_lookalike_host(client: TestClient) -> None:
    body = client.post(
        "/platforms/check-url",
        json={"page_url": "https://boards.greenhouse.io.evil.example/acme"},
    ).json()
    assert body["safety"]["allowed"] is False


def test_check_url_performs_no_outbound_request(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Checking a URL must never fetch the page.

    ``httpx`` is the only HTTP client in the backend's dependency tree, so breaking
    its transport is enough to prove the endpoint does not reach out. (The socket
    layer itself cannot be patched here: ``TestClient`` needs it to run the app.)
    """

    import httpx

    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("check-url must not make an outbound request")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", explode)

    response = client.post("/platforms/check-url", json={"page_url": GREENHOUSE_PAGE})
    assert response.status_code == 200


def test_check_url_writes_nothing_to_disk(client: TestClient, tmp_path: Path) -> None:
    before = sorted(p.name for p in tmp_path.iterdir())
    client.post("/platforms/check-url", json={"page_url": GREENHOUSE_PAGE})
    assert sorted(p.name for p in tmp_path.iterdir()) == before


# --- POST /extension/analyze-real-page: gating --------------------------------


def test_real_page_requires_user_confirmation(client: TestClient) -> None:
    _save_profile(client)
    response = _analyze_real(client, _contact_fields(), user_confirmed_real_page=False)
    assert response.status_code == 400
    assert "confirm" in response.json()["detail"].lower()


def test_unsupported_page_is_refused_even_when_confirmed(client: TestClient) -> None:
    _save_profile(client)
    response = _analyze_real(
        client, _contact_fields(), page_url="https://evil.example/apply"
    )
    assert response.status_code == 400
    assert response.json()["detail"]


def test_lookalike_host_is_refused(client: TestClient) -> None:
    _save_profile(client)
    response = _analyze_real(
        client,
        _contact_fields(),
        page_url="https://boards.greenhouse.io.evil.example/acme",
    )
    assert response.status_code == 400


def test_http_real_page_is_refused(client: TestClient) -> None:
    _save_profile(client)
    response = _analyze_real(
        client, _contact_fields(), page_url="http://boards.greenhouse.io/acme/jobs/1"
    )
    assert response.status_code == 400
    assert "https" in response.json()["detail"].lower()


def test_claimed_platform_id_cannot_widen_access(client: TestClient) -> None:
    """The backend re-derives the platform; a caller's claim is only a hint."""

    _save_profile(client)
    response = _analyze_real(
        client,
        _contact_fields(),
        page_url="https://evil.example/apply",
        platform_id=PLATFORM_GREENHOUSE,
        platform_confidence=1.0,
    )
    assert response.status_code == 400


def test_missing_profile_returns_404(client: TestClient) -> None:
    response = _analyze_real(client, _contact_fields())
    assert response.status_code == 404
    assert "profile" in response.json()["detail"].lower()


def test_approved_generic_domain_is_analyzed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(APPROVED_DOMAINS_ENV_VAR, "careers.acme-corp.example")
    _save_profile(client)
    response = _analyze_real(
        client,
        _contact_fields(),
        page_url="https://careers.acme-corp.example/apply",
        platform_id=PLATFORM_GENERIC,
    )
    assert response.status_code == 200
    assert response.json()["platform"]["platform_id"] == PLATFORM_GENERIC


def test_local_page_needs_no_confirmation(client: TestClient) -> None:
    _save_profile(client)
    response = _analyze_real(
        client,
        _contact_fields(),
        page_url=LOCAL_PAGE,
        platform_id=PLATFORM_LOCAL,
        user_confirmed_real_page=False,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["safety"]["requires_user_confirmation"] is False
    assert body["safety"]["platform_id"] == PLATFORM_LOCAL


# --- POST /extension/analyze-real-page: plan content --------------------------


def test_safe_fields_get_values_and_a_reviewable_plan(client: TestClient) -> None:
    _save_profile(client)
    body = _analyze_real(client, _contact_fields()).json()

    assert body["fill_plan"]["mappings"]
    by_id = {i["field_id"]: i for i in body["instructions"]}
    assert by_id["email"]["action"] == "fill"
    assert by_id["email"]["value"] == "ada@example.com"
    # The plan half is for display and carries only redacted previews.
    plan_by_id = {m["field_id"]: m for m in body["fill_plan"]["mappings"]}
    assert "ada@example.com" not in str(plan_by_id["email"]["value_preview"])


def test_sensitive_and_unsafe_fields_never_carry_values(client: TestClient) -> None:
    _save_profile(client)
    fields = [
        *_contact_fields(),
        _field("resume", label_text="Resume", input_type="file", is_file_upload=True),
        _field(
            "sponsorship",
            label_text="Will you require visa sponsorship?",
            tag_name="select",
            input_type=None,
            is_select=True,
            options=["Yes", "No"],
        ),
        _field("salary", label_text="Desired salary"),
        _field("gender", label_text="Gender", tag_name="select", is_select=True),
        _field("password", label_text="Password", input_type="password"),
        _field("apply", label_text="Submit application", is_submit_control=True),
    ]

    body = _analyze_real(client, fields).json()
    by_id = {i["field_id"]: i for i in body["instructions"]}

    for field_id in ["resume", "sponsorship", "salary", "gender", "apply"]:
        assert by_id[field_id]["value"] is None, field_id
    # Passwords are dropped before mapping, so they get no instruction at all.
    assert "password" not in by_id
    assert any("password" in warning.lower() for warning in body["warnings"])


def test_custom_controls_are_downgraded_and_counted(client: TestClient) -> None:
    _save_profile(client)
    fields = [
        *_contact_fields(),
        _field(
            "school",
            label_text="School",
            tag_name="div",
            input_type=None,
            is_custom_control=True,
            unsupported_reason="ARIA combobox",
        ),
    ]

    body = _analyze_real(client, fields).json()
    by_id = {m["field_id"]: m for m in body["fill_plan"]["mappings"]}
    assert by_id["school"]["action"] == "manual_review"
    assert body["unsupported_count"] == 1
    instruction = next(i for i in body["instructions"] if i["field_id"] == "school")
    assert instruction["value"] is None


def test_empty_field_list_is_explained_rather_than_erroring(client: TestClient) -> None:
    _save_profile(client)
    response = _analyze_real(client, [])
    assert response.status_code == 200
    body = response.json()
    assert body["fill_plan"]["mappings"] == []
    assert body["instructions"] == []
    assert any("no fields were detected" in w.lower() for w in body["warnings"])


def test_profile_needing_review_is_warned_about(client: TestClient) -> None:
    _save_profile(client, needs_review=True)
    body = _analyze_real(client, _contact_fields()).json()
    assert any("needing review" in warning for warning in body["warnings"])


def test_response_always_carries_the_review_reminder(client: TestClient) -> None:
    _save_profile(client)
    body = _analyze_real(client, _contact_fields()).json()
    assert any("review every field" in warning.lower() for warning in body["warnings"])


def test_platform_signal_disagreement_is_recorded(client: TestClient) -> None:
    _save_profile(client)
    body = _analyze_real(client, _contact_fields(), platform_id="lever").json()
    # URL wins; the extension's guess is kept as evidence, not as authority.
    assert body["platform"]["platform_id"] == PLATFORM_GREENHOUSE
    assert "page-signal:lever" in body["platform"]["matched_by"]


def test_analysis_writes_nothing_to_disk(client: TestClient, tmp_path: Path) -> None:
    _save_profile(client)
    before = {p.name for p in tmp_path.rglob("*")}
    _analyze_real(client, _contact_fields())
    assert {p.name for p in tmp_path.rglob("*")} == before


# --- Phase 6 behaviour is unchanged -------------------------------------------


def test_phase6_endpoint_still_rejects_real_pages(client: TestClient) -> None:
    _save_profile(client)
    response = client.post(
        "/extension/analyze-page",
        json={"page_url": GREENHOUSE_PAGE, "fields": _contact_fields()},
    )
    assert response.status_code == 400


def test_phase6_endpoint_still_works_on_local_pages(client: TestClient) -> None:
    _save_profile(client)
    response = client.post(
        "/extension/analyze-page",
        json={"page_url": LOCAL_PAGE, "form_name": "basic", "fields": _contact_fields()},
    )
    assert response.status_code == 200
    assert response.json()["fill_plan"]["mappings"]


def test_phase6_request_bodies_validate_without_phase7_fields(client: TestClient) -> None:
    """The new detected-field flags are optional, so old payloads still work."""

    _save_profile(client)
    minimal = {
        "field_id": "email",
        "selector": "#email",
        "tag_name": "input",
        "input_type": "email",
        "label_text": "Email",
    }
    response = client.post(
        "/extension/analyze-page",
        json={"page_url": LOCAL_PAGE, "form_name": "basic", "fields": [minimal]},
    )
    assert response.status_code == 200


# --- static fixture mount -----------------------------------------------------


def test_fixture_pages_are_served_read_only(client: TestClient) -> None:
    response = client.get("/test-fixtures/platform-pages/greenhouse-like.html")
    assert response.status_code == 200
    assert "<form" in response.text.lower()


def test_fixture_mount_blocks_path_traversal(client: TestClient) -> None:
    response = client.get("/test-fixtures/../backend/app/main.py")
    assert response.status_code in {404, 403, 400}


def test_fixture_mount_rejects_writes(client: TestClient) -> None:
    response = client.post("/test-fixtures/platform-pages/greenhouse-like.html")
    assert response.status_code in {404, 405}
