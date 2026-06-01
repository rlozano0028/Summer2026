"""Tests for the Phase 1 candidate profile schema."""

from __future__ import annotations

import json

from app.models.candidate_profile import CandidateProfile, WorkAuthorization


def test_candidate_profile_minimal_creation() -> None:
    """A profile can be created with no data and have sane defaults."""

    profile = CandidateProfile()

    assert profile.identity.full_name is None
    assert profile.education == []
    assert profile.experience == []
    assert profile.projects == []
    assert profile.skills.programming_languages == []
    assert profile.metadata.needs_review is False


def test_work_authorization_defaults_to_none() -> None:
    """Sensitive work-authorization fields default to None, not False."""

    auth = WorkAuthorization()

    assert auth.authorized_to_work_us is None
    assert auth.requires_sponsorship is None
    assert auth.notes is None

    # And on a full profile too.
    profile = CandidateProfile()
    assert profile.work_authorization.authorized_to_work_us is None
    assert profile.work_authorization.requires_sponsorship is None


def test_profile_serializes_cleanly_to_json() -> None:
    """The profile round-trips through JSON without errors."""

    profile = CandidateProfile()
    raw = profile.model_dump_json()
    data = json.loads(raw)

    assert "identity" in data
    assert "work_authorization" in data
    assert data["work_authorization"]["authorized_to_work_us"] is None

    # Re-parse to confirm the JSON is valid for the model.
    reparsed = CandidateProfile.model_validate_json(raw)
    assert reparsed == profile
