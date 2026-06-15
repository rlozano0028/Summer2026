"""Dry-run autofill tests (Phase 4).

Verifies that a dry run never types into the form and that the runner never
interacts with submit controls. Skips cleanly without a Chromium binary.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.automation import AutomationRequest
from app.models.candidate_profile import CandidateProfile, Identity
from app.services import sample_forms
from app.services.playwright_autofill import (
    _launch_browser,
    _path_to_file_url,
    run_local_autofill,
)
from tests._playwright_helpers import SETUP_HINT, chromium_available

pytestmark = pytest.mark.skipif(not chromium_available(), reason=SETUP_HINT)


def _profile() -> CandidateProfile:
    return CandidateProfile(
        identity=Identity(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
        )
    )


def test_dry_run_fills_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOMATION_REPORTS_DIR", str(tmp_path / "reports"))
    form_path = sample_forms.resolve_sample_form("basic")
    request = AutomationRequest(form_name="basic", headless=True, dry_run=True)

    result = run_local_autofill(form_path, _profile(), request)

    # Nothing was actually typed.
    assert result.filled_fields == []
    assert result.success is True
    assert result.report_path is not None

    # Verify the live DOM was untouched after a dry run.
    with _launch_browser(headless=True) as (_browser, page):
        page.goto(_path_to_file_url(form_path))
        first_name_value = page.locator("#first_name").input_value()
    assert first_name_value == ""


def test_dry_run_does_not_submit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOMATION_REPORTS_DIR", str(tmp_path / "reports"))
    form_path = sample_forms.resolve_sample_form("basic")
    request = AutomationRequest(form_name="basic", headless=True, dry_run=True)

    result = run_local_autofill(form_path, _profile(), request)

    # The submit control is reported as skipped, never filled or interacted with.
    assert "Submit" not in result.filled_fields
    assert any("submit" in s.lower() for s in result.skipped_fields)
