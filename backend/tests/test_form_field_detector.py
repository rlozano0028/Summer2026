"""Tests for Playwright-based form field detection (Phase 4).

These require a Chromium binary and skip cleanly if it is not installed. They
only ever open the local sample form (no network).
"""

from __future__ import annotations

import pytest

from app.services import sample_forms
from app.services.form_field_detector import detect_form_fields
from app.services.playwright_autofill import _launch_browser, _path_to_file_url
from tests._playwright_helpers import SETUP_HINT, chromium_available

pytestmark = pytest.mark.skipif(not chromium_available(), reason=SETUP_HINT)


def _detect_basic_form():
    form_path = sample_forms.resolve_sample_form("basic")
    with _launch_browser(headless=True) as (_browser, page):
        page.goto(_path_to_file_url(form_path))
        return detect_form_fields(page)


def test_detects_expected_fields() -> None:
    fields = _detect_basic_form()
    names = {f.name for f in fields if f.name}
    assert {"first_name", "last_name", "email", "skills"}.issubset(names)


def test_detects_label_text_and_selectors() -> None:
    fields = _detect_basic_form()
    email = next(f for f in fields if f.name == "email")
    assert email.label_text is not None
    assert "email" in email.label_text.lower()
    # id is preferred for the selector.
    assert email.selector == "#email"


def test_detects_file_upload_and_submit() -> None:
    fields = _detect_basic_form()
    assert any(f.is_file_upload for f in fields)
    assert any(f.is_submit_control for f in fields)
