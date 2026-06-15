"""Storage for redacted automation reports (Phase 4).

Reports are written as JSON under ``backend/app/data/automation-reports/``. They
are intentionally redacted: an :class:`AutofillResult` records only field
identifiers, actions, and warnings - never full profile values or resume text.

The directory can be overridden with the ``AUTOMATION_REPORTS_DIR`` environment
variable (used by tests so they never touch real report files).
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from app.models.automation import AutofillResult

REPORTS_DIR_ENV_VAR = "AUTOMATION_REPORTS_DIR"

# Default: backend/app/data/automation-reports (relative to this file).
_DEFAULT_REPORTS_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "automation-reports"
)


def get_reports_dir() -> Path:
    """Return the directory where automation reports are stored."""

    override = os.environ.get(REPORTS_DIR_ENV_VAR)
    return Path(override) if override else _DEFAULT_REPORTS_DIR


def _safe_form_name(form_name: str) -> str:
    """Sanitize a form name for use in a filename."""

    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", form_name.strip().lower())
    return cleaned.strip("-") or "form"


def save_report(result: AutofillResult) -> Path:
    """Persist a redacted report as JSON and return its path.

    The report directory is created if needed. Pydantic serialization only
    includes the fields defined on :class:`AutofillResult`, which by design
    contain no raw profile values.
    """

    reports_dir = get_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{timestamp}-{_safe_form_name(result.form_name)}.json"
    path = reports_dir / filename
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return path
