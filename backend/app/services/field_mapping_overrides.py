"""Local, user-controlled mapping overrides (Phase 5).

Overrides let a user correct or pin how a specific field on a specific local
sample form should be handled, so the decision is reused on future runs. They
are stored as JSON under ``backend/app/data/mapping-overrides/`` (git-ignored)
and are matched by ``form_name`` + a stable ``field_fingerprint``.

Privacy: a fingerprint is derived only from non-private field metadata (label,
name, id, placeholder, input type, tag name). No profile values are ever stored
in an override file.

Safety: this module only stores overrides. The mapper is responsible for
refusing to autofill sensitive fields even when an override asks for it.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models.automation import ALLOWED_ACTIONS
from app.models.field_mapping import FieldContext, MappingOverride

OVERRIDES_DIR_ENV_VAR = "MAPPING_OVERRIDES_DIR"

# backend/app/services/field_mapping_overrides.py -> backend/app/data/...
_DEFAULT_OVERRIDES_DIR = (
    Path(__file__).resolve().parent.parent / "data" / "mapping-overrides"
)


class MappingOverrideError(RuntimeError):
    """Raised when an override file cannot be read or written."""


def get_overrides_dir() -> Path:
    """Return the directory where override JSON files live."""

    override = os.environ.get(OVERRIDES_DIR_ENV_VAR)
    return Path(override) if override else _DEFAULT_OVERRIDES_DIR


def _safe_form_name(form_name: str) -> str:
    safe = "".join(c if c.isalnum() else "-" for c in form_name.strip().lower())
    return safe.strip("-") or "form"


def _form_file(form_name: str) -> Path:
    return get_overrides_dir() / f"{_safe_form_name(form_name)}.json"


def compute_field_fingerprint(
    *,
    label_text: Optional[str],
    name: Optional[str],
    id_attribute: Optional[str],
    placeholder: Optional[str],
    input_type: Optional[str],
    tag_name: Optional[str],
) -> str:
    """Return a stable fingerprint from non-private field metadata.

    The fingerprint is deterministic for the same field metadata across runs and
    contains no profile data.
    """

    parts = [
        (label_text or "").strip().lower(),
        (name or "").strip().lower(),
        (id_attribute or "").strip().lower(),
        (placeholder or "").strip().lower(),
        (input_type or "").strip().lower(),
        (tag_name or "").strip().lower(),
    ]
    payload = "||".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def fingerprint_for_context(context: FieldContext) -> str:
    """Convenience wrapper to fingerprint a :class:`FieldContext`."""

    return compute_field_fingerprint(
        label_text=context.label_text,
        name=context.name,
        id_attribute=context.id_attribute,
        placeholder=context.placeholder,
        input_type=context.input_type,
        tag_name=context.tag_name,
    )


def _read_form_overrides(form_name: str) -> list[MappingOverride]:
    path = _form_file(form_name)
    if not path.is_file():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem error
        raise MappingOverrideError(f"Could not read overrides: {exc}") from exc
    if not raw.strip():
        return []
    try:
        import json

        data = json.loads(raw)
        return [MappingOverride.model_validate(item) for item in data]
    except Exception as exc:  # noqa: BLE001 - corrupt file
        raise MappingOverrideError(f"Corrupt override file {path}: {exc}") from exc


def _write_form_overrides(form_name: str, overrides: list[MappingOverride]) -> None:
    path = _form_file(form_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    import json

    payload = [o.model_dump(mode="json") for o in overrides]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_overrides(form_name: Optional[str] = None) -> list[MappingOverride]:
    """Load overrides for one form, or all overrides if ``form_name`` is None."""

    directory = get_overrides_dir()
    if form_name is not None:
        return _read_form_overrides(form_name)
    if not directory.is_dir():
        return []
    all_overrides: list[MappingOverride] = []
    for path in sorted(directory.glob("*.json")):
        stem = path.stem
        all_overrides.extend(_read_form_overrides(stem))
    return all_overrides


def find_override(form_name: str, field_fingerprint: str) -> Optional[MappingOverride]:
    """Return the override matching ``form_name`` + ``field_fingerprint``, if any."""

    for override in _read_form_overrides(form_name):
        if override.field_fingerprint == field_fingerprint:
            return override
    return None


def save_override(override: MappingOverride) -> MappingOverride:
    """Create or update an override (matched by form + fingerprint).

    Validates the action and timestamps the record. Returns the stored override.
    """

    if override.action not in ALLOWED_ACTIONS:
        raise MappingOverrideError(
            f"Invalid action '{override.action}'. Allowed: {sorted(ALLOWED_ACTIONS)}."
        )

    now = datetime.now(timezone.utc)
    overrides = _read_form_overrides(override.form_name)

    updated: Optional[MappingOverride] = None
    remaining: list[MappingOverride] = []
    for existing in overrides:
        same_fingerprint = existing.field_fingerprint == override.field_fingerprint
        same_id = existing.override_id == override.override_id
        if same_fingerprint or same_id:
            updated = override.model_copy(
                update={
                    "override_id": existing.override_id,
                    "created_at": existing.created_at,
                    "updated_at": now,
                }
            )
        else:
            remaining.append(existing)

    if updated is None:
        updated = override.model_copy(
            update={"created_at": now, "updated_at": now}
        )

    remaining.append(updated)
    _write_form_overrides(override.form_name, remaining)
    return updated


def delete_override(override_id: str) -> bool:
    """Delete an override by id across all forms. Returns True if removed."""

    directory = get_overrides_dir()
    if not directory.is_dir():
        return False
    for path in sorted(directory.glob("*.json")):
        overrides = _read_form_overrides(path.stem)
        remaining = [o for o in overrides if o.override_id != override_id]
        if len(remaining) != len(overrides):
            _write_form_overrides(path.stem, remaining)
            return True
    return False
