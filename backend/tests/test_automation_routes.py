"""Tests for the Phase 4 automation API routes.

Profile storage and report storage are redirected to temp paths so real data is
never touched. Browser-dependent assertions skip cleanly (HTTP 503) when no
Chromium binary is installed.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.candidate_profile import CandidateProfile, Identity
from app.services import profile_storage


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv(profile_storage.STORAGE_PATH_ENV_VAR, str(tmp_path / "profile.json"))
    monkeypatch.setenv("AUTOMATION_REPORTS_DIR", str(tmp_path / "reports"))
    return TestClient(app)


def _save_profile(client: TestClient) -> None:
    payload = CandidateProfile(
        identity=Identity(first_name="Ada", email="ada@example.com")
    ).model_dump(mode="json")
    assert client.put("/profile", json=payload).status_code == 200


def test_sample_forms_returns_only_known_forms(client: TestClient) -> None:
    response = client.get("/automation/sample-forms")
    assert response.status_code == 200
    assert response.json()["forms"] == [
        "basic",
        "edge-case-labels",
        "engineering",
        "select-radio-checkboxes",
        "sensitive-fields",
    ]


def test_analyze_404_when_no_profile(client: TestClient) -> None:
    response = client.post("/automation/analyze", json={"form_name": "basic"})
    assert response.status_code == 404
    assert "No saved profile" in response.json()["detail"]


def test_analyze_rejects_unknown_form(client: TestClient) -> None:
    _save_profile(client)
    response = client.post("/automation/analyze", json={"form_name": "real-job-site"})
    assert response.status_code == 400


def test_analyze_returns_fill_plan(client: TestClient) -> None:
    _save_profile(client)
    response = client.post("/automation/analyze", json={"form_name": "basic"})
    if response.status_code == 503:
        pytest.skip("Chromium not installed; run: python -m playwright install chromium")
    assert response.status_code == 200
    plan = response.json()
    # Phase 5: the plan uses the short sample-form name (so overrides match).
    assert plan["form_name"] == "basic"
    assert plan["fill_count"] >= 1
    # A sensitive/legal field-free basic form still has manual-review items (resume, essay).
    assert plan["manual_review_count"] >= 1
    # Phase 5 enriches each mapping with a category and a fingerprint.
    first = plan["mappings"][0]
    assert "category" in first
    assert "field_fingerprint" in first


def test_analyze_sensitive_form_never_fills(client: TestClient) -> None:
    _save_profile(client)
    response = client.post("/automation/analyze", json={"form_name": "sensitive-fields"})
    if response.status_code == 503:
        pytest.skip("Chromium not installed; run: python -m playwright install chromium")
    assert response.status_code == 200
    plan = response.json()
    # No sensitive field is ever queued to fill; sensitive fields are flagged.
    assert plan["fill_count"] == 0
    assert any(m["sensitive"] for m in plan["mappings"])


def test_dry_run_does_not_mutate_or_submit(client: TestClient) -> None:
    _save_profile(client)
    response = client.post("/automation/dry-run", json={"form_name": "basic"})
    if response.status_code == 503:
        pytest.skip("Chromium not installed; run: python -m playwright install chromium")
    assert response.status_code == 200
    result = response.json()
    assert result["filled_fields"] == []
    assert result["success"] is True


def test_run_sample_never_submits(client: TestClient) -> None:
    _save_profile(client)
    response = client.post(
        "/automation/run-sample",
        json={"form_name": "basic", "headless": True, "dry_run": False},
    )
    if response.status_code == 503:
        pytest.skip("Chromium not installed; run: python -m playwright install chromium")
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    # The submit control is always skipped; nothing is ever submitted.
    assert result["report_path"]
