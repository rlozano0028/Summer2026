"""Registry of approved local sample forms (Phase 4).

Only the forms listed here may be automated. Phase 4 never accepts arbitrary
URLs or external sites - everything is a local file shipped in this repo.

The sample-forms directory lives at the repository root. It can be overridden
with the ``SAMPLE_FORMS_DIR`` environment variable (useful for tests).
"""

from __future__ import annotations

import os
from pathlib import Path

SAMPLE_FORMS_DIR_ENV_VAR = "SAMPLE_FORMS_DIR"

# backend/app/services/sample_forms.py -> repo root is parents[3].
_DEFAULT_SAMPLE_FORMS_DIR = Path(__file__).resolve().parents[3] / "sample-forms"

# Map of short form name -> HTML filename. This is the allow-list.
KNOWN_FORMS: dict[str, str] = {
    "basic": "basic-application.html",
    "engineering": "engineering-application.html",
    "edge-case-labels": "edge-case-labels.html",
    "sensitive-fields": "sensitive-fields.html",
    "select-radio-checkboxes": "select-radio-checkboxes.html",
}


class UnknownSampleFormError(ValueError):
    """Raised when a requested form name is not in the allow-list."""


def get_sample_forms_dir() -> Path:
    """Return the directory containing the sample HTML forms."""

    override = os.environ.get(SAMPLE_FORMS_DIR_ENV_VAR)
    return Path(override) if override else _DEFAULT_SAMPLE_FORMS_DIR


def list_sample_forms() -> list[str]:
    """Return the sorted list of known sample form names."""

    return sorted(KNOWN_FORMS)


def resolve_sample_form(form_name: str) -> Path:
    """Resolve a known form name to its local HTML path.

    Raises:
        UnknownSampleFormError: the name is not in the allow-list.
        FileNotFoundError: the file is missing on disk.
    """

    key = form_name.strip().lower()
    if key not in KNOWN_FORMS:
        known = ", ".join(list_sample_forms())
        raise UnknownSampleFormError(
            f"Unknown sample form '{form_name}'. Known forms: {known}."
        )
    path = get_sample_forms_dir() / KNOWN_FORMS[key]
    if not path.is_file():
        raise FileNotFoundError(f"Sample form file not found: {path}")
    return path
