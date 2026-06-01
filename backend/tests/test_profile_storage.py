"""Tests for the Phase 3 local profile storage service.

Every test redirects storage to a temporary path via the
``PROFILE_STORAGE_PATH`` environment variable, so no real profile is touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.candidate_profile import CandidateProfile, Identity
from app.services import profile_storage


@pytest.fixture
def temp_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point profile storage at an isolated temp file for the test."""

    storage_file = tmp_path / "profile.json"
    monkeypatch.setenv(profile_storage.STORAGE_PATH_ENV_VAR, str(storage_file))
    return storage_file


def _sample_profile() -> CandidateProfile:
    return CandidateProfile(identity=Identity(full_name="Jane Doe", email="jane@example.com"))


def test_storage_path_honors_env_override(temp_storage: Path) -> None:
    assert profile_storage.get_profile_storage_path() == temp_storage


def test_save_and_load_round_trip(temp_storage: Path) -> None:
    assert profile_storage.profile_exists() is False
    assert profile_storage.load_profile() is None

    saved = profile_storage.save_profile(_sample_profile())
    assert temp_storage.is_file()
    assert profile_storage.profile_exists() is True

    loaded = profile_storage.load_profile()
    assert loaded is not None
    assert loaded.identity.full_name == "Jane Doe"
    assert loaded == saved


def test_delete_profile(temp_storage: Path) -> None:
    assert profile_storage.delete_profile() is False  # nothing yet

    profile_storage.save_profile(_sample_profile())
    assert profile_storage.delete_profile() is True
    assert profile_storage.profile_exists() is False


def test_load_corrupted_profile_raises(temp_storage: Path) -> None:
    temp_storage.write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(profile_storage.ProfileStorageError):
        profile_storage.load_profile()
