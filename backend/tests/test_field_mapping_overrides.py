"""Tests for the Phase 5 local mapping-override store."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models.field_mapping import FieldCategory, MappingOverride
from app.services import field_mapping_overrides as overrides


@pytest.fixture(autouse=True)
def _temp_overrides_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(overrides.OVERRIDES_DIR_ENV_VAR, str(tmp_path / "mapping-overrides"))
    return tmp_path


def _override(**kwargs) -> MappingOverride:
    now = datetime.now(timezone.utc)
    defaults = dict(
        override_id="ov1",
        form_name="basic",
        field_fingerprint="fp-abc",
        category=FieldCategory.IDENTITY_FIRST_NAME.value,
        profile_path="identity.first_name",
        action="suggest",
        note=None,
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return MappingOverride(**defaults)


def test_saves_and_loads_override() -> None:
    overrides.save_override(_override())
    loaded = overrides.load_overrides("basic")
    assert len(loaded) == 1
    assert loaded[0].field_fingerprint == "fp-abc"


def test_finds_override_by_form_and_fingerprint() -> None:
    overrides.save_override(_override())
    found = overrides.find_override("basic", "fp-abc")
    assert found is not None
    missing = overrides.find_override("basic", "nope")
    assert missing is None


def test_deletes_override() -> None:
    saved = overrides.save_override(_override())
    assert overrides.delete_override(saved.override_id) is True
    assert overrides.load_overrides("basic") == []
    assert overrides.delete_override("does-not-exist") is False


def test_fingerprint_is_stable_and_metadata_only() -> None:
    fp1 = overrides.compute_field_fingerprint(
        label_text="First name", name="first_name", id_attribute="first_name",
        placeholder=None, input_type="text", tag_name="input",
    )
    fp2 = overrides.compute_field_fingerprint(
        label_text="First name", name="first_name", id_attribute="first_name",
        placeholder=None, input_type="text", tag_name="input",
    )
    assert fp1 == fp2
    fp3 = overrides.compute_field_fingerprint(
        label_text="Last name", name="last_name", id_attribute="last_name",
        placeholder=None, input_type="text", tag_name="input",
    )
    assert fp1 != fp3


def test_override_file_contains_no_profile_values() -> None:
    overrides.save_override(_override(note="ada@example.com is mine"))
    directory = overrides.get_overrides_dir()
    files = list(directory.glob("*.json"))
    assert files
    contents = files[0].read_text(encoding="utf-8")
    # The fingerprint and category are stored; profile values are never stored.
    assert "fp-abc" in contents
    # The note is user text we persist verbatim, but no resolved profile value
    # is ever written by the store itself.
    assert "identity.first_name" in contents
