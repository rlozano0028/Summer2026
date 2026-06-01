"""Tests for the Phase 3 profile API routes.

Storage is redirected to a temp path via ``PROFILE_STORAGE_PATH`` so the real
profile is never touched. Tests are isolated and repeatable.
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
    storage_file = tmp_path / "profile.json"
    monkeypatch.setenv(profile_storage.STORAGE_PATH_ENV_VAR, str(storage_file))
    return TestClient(app)


def _profile_payload() -> dict:
    return CandidateProfile(
        identity=Identity(full_name="Jane Doe", email="jane@example.com")
    ).model_dump(mode="json")


def test_get_profile_404_when_missing(client: TestClient) -> None:
    response = client.get("/profile")
    assert response.status_code == 404
    assert "No saved profile" in response.json()["detail"]


def test_put_profile_saves_and_returns(client: TestClient) -> None:
    response = client.put("/profile", json=_profile_payload())
    assert response.status_code == 200
    assert response.json()["identity"]["full_name"] == "Jane Doe"

    # And a subsequent GET now returns it.
    getter = client.get("/profile")
    assert getter.status_code == 200
    assert getter.json()["identity"]["email"] == "jane@example.com"


def test_patch_review_status_updates_needs_review(client: TestClient) -> None:
    client.put("/profile", json=_profile_payload())

    response = client.patch(
        "/profile/review-status",
        json={"needs_review": False, "review_note": "Reviewed on local dashboard."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["needs_review"] is False
    assert any("Reviewed on local dashboard." in note for note in body["metadata"]["review_notes"])


def test_patch_review_status_404_when_missing(client: TestClient) -> None:
    response = client.patch("/profile/review-status", json={"needs_review": False})
    assert response.status_code == 404


def test_delete_profile_removes_saved_profile(client: TestClient) -> None:
    client.put("/profile", json=_profile_payload())

    deleted = client.delete("/profile")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    # Deleting again reports nothing to delete.
    again = client.delete("/profile")
    assert again.json()["deleted"] is False
    assert client.get("/profile").status_code == 404


def test_parse_and_save_persists_profile(client: TestClient) -> None:
    resume_text = (
        "Jane Doe\njane.doe@example.com\nhttps://github.com/janedoe\n"
        "Skills: Python, FastAPI, Docker"
    )
    files = {"file": ("resume.txt", resume_text.encode("utf-8"), "text/plain")}

    response = client.post("/resume/parse-and-save", files=files)
    assert response.status_code == 200
    result = response.json()
    assert result["profile"]["identity"]["email"] == "jane.doe@example.com"
    assert result["profile"]["metadata"]["needs_review"] is True

    # The profile was actually saved and is now retrievable.
    getter = client.get("/profile")
    assert getter.status_code == 200
    assert getter.json()["identity"]["email"] == "jane.doe@example.com"
