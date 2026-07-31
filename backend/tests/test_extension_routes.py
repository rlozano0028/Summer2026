"""Tests for the Phase 6 extension API routes.

Profile storage and the mapping-override store are redirected to temp paths so
real personal data is never read or written. No Chrome, no extension, and no
network calls are involved: the routes only analyze field metadata.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.candidate_profile import CandidateProfile, Identity, Links
from app.services import field_mapping_overrides, profile_storage

LOCAL_PAGE = "http://127.0.0.1:8000/sample-forms/basic-application.html"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv(profile_storage.STORAGE_PATH_ENV_VAR, str(tmp_path / "profile.json"))
    monkeypatch.setenv(
        field_mapping_overrides.OVERRIDES_DIR_ENV_VAR, str(tmp_path / "overrides")
    )
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


def _analyze(client: TestClient, fields: list[dict[str, object]], **kwargs: object) -> object:
    body: dict[str, object] = {
        "page_url": LOCAL_PAGE,
        "page_title": "Basic Application",
        "form_name": "basic",
        "fields": fields,
    }
    body.update(kwargs)
    return client.post("/extension/analyze-page", json=body)


# --- /extension/health -------------------------------------------------------


def test_health_reports_missing_profile_clearly(client: TestClient) -> None:
    response = client.get("/extension/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["profile_exists"] is False
    assert body["profile_needs_review"] is None
    assert "no saved profile" in body["message"].lower()


def test_health_reports_saved_profile_status(client: TestClient) -> None:
    _save_profile(client, needs_review=True)
    body = client.get("/extension/health").json()
    assert body["ok"] is True
    assert body["profile_exists"] is True
    assert body["profile_needs_review"] is True
    assert body["backend"]


# --- /extension/validate-page ------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/sample-forms/basic-application.html",
        "http://localhost:8000/x.html",
        "http://127.0.0.1:5173/",
        "http://localhost:8080/form",
    ],
)
def test_validate_page_allows_local_dev_origins(client: TestClient, url: str) -> None:
    body = client.post("/extension/validate-page", json={"page_url": url}).json()
    assert body["allowed"] is True


@pytest.mark.parametrize(
    "url",
    [
        "https://boards.greenhouse.io/example/jobs/1",
        "http://127.0.0.1:9999/x.html",
        "http://127.0.0.1.evil.example.com:8000/x.html",
        "file:///C:/forms/basic-application.html",
        "not-a-url",
    ],
)
def test_validate_page_rejects_everything_else(client: TestClient, url: str) -> None:
    body = client.post("/extension/validate-page", json={"page_url": url}).json()
    assert body["allowed"] is False
    assert body["allowed_origins"]


# --- /extension/analyze-page -------------------------------------------------


def test_analyze_page_404_when_profile_missing(client: TestClient) -> None:
    response = _analyze(client, [_field("f1", name="email")])
    assert response.status_code == 404
    assert "No saved profile" in response.json()["detail"]


def test_analyze_page_rejects_non_local_page(client: TestClient) -> None:
    _save_profile(client)
    response = _analyze(
        client,
        [_field("f1", name="email")],
        page_url="https://boards.greenhouse.io/example/jobs/1",
    )
    assert response.status_code == 400
    assert "local development pages" in response.json()["detail"]


def test_analyze_page_rejects_empty_field_list(client: TestClient) -> None:
    _save_profile(client)
    response = _analyze(client, [])
    assert response.status_code == 400
    assert "Detect fields" in response.json()["detail"]


def test_analyze_page_returns_plan_and_instructions(client: TestClient) -> None:
    _save_profile(client)
    fields = [
        _field("f1", selector="#first_name", name="first_name", label_text="First name"),
        _field("f2", selector="#email", input_type="email", name="email", label_text="Email"),
    ]
    response = _analyze(client, fields)
    assert response.status_code == 200
    body = response.json()

    assert body["page_url"] == LOCAL_PAGE
    assert body["page_title"] == "Basic Application"
    assert body["profile_review_status"] is False
    plan = body["fill_plan"]
    assert plan["form_name"] == "basic"
    assert plan["fill_count"] >= 1
    # Phase 5 enrichment survives the extension path.
    assert "category" in plan["mappings"][0]
    assert "field_fingerprint" in plan["mappings"][0]
    # One instruction per mapping, correlated by field_id.
    assert len(body["instructions"]) == len(plan["mappings"])
    assert {i["field_id"] for i in body["instructions"]} == {"f1", "f2"}


def test_analyze_page_normalizes_sample_form_name(client: TestClient) -> None:
    """A sample-form page resolves to its short name so dashboard overrides apply."""

    _save_profile(client)
    # The popup sends the page's file name; the backend maps it to "basic".
    response = _analyze(
        client, [_field("f1", name="email")], form_name="basic-application.html"
    )
    assert response.status_code == 200
    assert response.json()["fill_plan"]["form_name"] == "basic"


def test_analyze_page_defaults_form_name_for_unknown_page(client: TestClient) -> None:
    _save_profile(client)
    response = _analyze(
        client,
        [_field("f1", name="email")],
        page_url="http://127.0.0.1:5173/",
        form_name=None,
    )
    assert response.status_code == 200
    assert response.json()["fill_plan"]["form_name"] == "extension-page"


def test_analyze_page_warns_when_profile_needs_review(client: TestClient) -> None:
    _save_profile(client, needs_review=True)
    body = _analyze(client, [_field("f1", name="email")]).json()
    assert body["profile_review_status"] is True
    assert any("needing review" in w for w in body["warnings"])


# --- /sample-forms static hosting (Phase 6) ----------------------------------


def test_sample_forms_are_served_over_http(client: TestClient) -> None:
    """The extension needs http pages; file:// is awkward for content scripts."""

    response = client.get("/sample-forms/basic-application.html")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<form" in response.text


def test_sample_forms_mount_rejects_unknown_and_traversal(client: TestClient) -> None:
    assert client.get("/sample-forms/does-not-exist.html").status_code == 404
    assert client.get("/sample-forms/../app/data/profile.json").status_code == 404


def test_analyze_page_does_not_open_a_browser(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The extension path must never touch the Playwright runner."""

    import app.services.playwright_autofill as playwright_autofill

    def _explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("extension analysis must not drive a browser")

    monkeypatch.setattr(playwright_autofill, "analyze_local_form", _explode)
    monkeypatch.setattr(playwright_autofill, "run_local_autofill", _explode)

    _save_profile(client)
    assert _analyze(client, [_field("f1", name="email")]).status_code == 200
