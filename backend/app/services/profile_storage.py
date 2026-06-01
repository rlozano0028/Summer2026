"""Local JSON storage for the reviewed candidate profile (Phase 3).

The reviewed profile is persisted as a single JSON file on disk. This is the
only candidate data we keep - uploaded resume files are never stored
permanently.

The storage location is resolved by :func:`get_profile_storage_path` and can be
overridden with the ``PROFILE_STORAGE_PATH`` environment variable. Tests rely on
this override (or monkeypatching the function) so they never touch a real
profile.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from app.models.candidate_profile import CandidateProfile

# Environment variable used to redirect storage (primarily for tests / advanced
# local setups).
STORAGE_PATH_ENV_VAR = "PROFILE_STORAGE_PATH"

# Default: backend/app/data/profile.json (relative to this file).
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DEFAULT_PROFILE_PATH = _DEFAULT_DATA_DIR / "profile.json"


class ProfileStorageError(RuntimeError):
    """Raised when a stored profile exists but cannot be read/parsed."""


def get_profile_storage_path() -> Path:
    """Return the path where the profile JSON is stored.

    Honors the ``PROFILE_STORAGE_PATH`` environment variable when set.
    """

    override = os.environ.get(STORAGE_PATH_ENV_VAR)
    return Path(override) if override else _DEFAULT_PROFILE_PATH


def profile_exists() -> bool:
    """Return True if a saved profile file exists."""

    return get_profile_storage_path().is_file()


def save_profile(profile: CandidateProfile) -> CandidateProfile:
    """Persist the profile as pretty-printed JSON and return it."""

    path = get_profile_storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return profile


def load_profile() -> Optional[CandidateProfile]:
    """Load the saved profile, or return None if none exists.

    Raises:
        ProfileStorageError: a file exists but cannot be parsed as a profile.
    """

    path = get_profile_storage_path()
    if not path.is_file():
        return None
    try:
        return CandidateProfile.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - wrap any read/parse failure.
        raise ProfileStorageError(
            f"Saved profile at '{path}' could not be read: {exc}"
        ) from exc


def delete_profile() -> bool:
    """Delete the saved profile. Returns True if a file was removed."""

    path = get_profile_storage_path()
    if path.is_file():
        path.unlink()
        return True
    return False
