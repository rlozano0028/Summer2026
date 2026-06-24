"""Local mapping-override API routes (Phase 5).

Overrides are local-only and user-controlled. They let a user pin how a specific
field on a specific local sample form should be handled. They never allow
autofilling a sensitive / legal field: any attempt to force ``fill`` on a
sensitive category is downgraded to ``manual_review`` with a warning.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.automation import ACTION_FILL, ACTION_MANUAL_REVIEW, ALLOWED_ACTIONS, FillPlan
from app.models.field_mapping import SENSITIVE_CATEGORIES, MappingOverride
from app.services import field_mapping_overrides, profile_storage, sample_forms
from app.services.playwright_autofill import PlaywrightSetupError, analyze_local_form

router = APIRouter(prefix="/mapping-overrides", tags=["mapping-overrides"])


class MappingOverrideCreate(BaseModel):
    """Body for creating / updating a mapping override.

    ``override_id`` is optional; when omitted a new id is generated. Timestamps
    are always set server-side.
    """

    override_id: Optional[str] = None
    form_name: str
    field_fingerprint: str
    category: str
    profile_path: Optional[str] = None
    action: str
    note: Optional[str] = None


class SaveOverrideResponse(BaseModel):
    """Response wrapping the saved override and any safety warnings."""

    override: MappingOverride
    warnings: list[str] = []


class ApplyToPlanRequest(BaseModel):
    """Body for POST /mapping-overrides/apply-to-plan."""

    form_name: str


@router.get("", response_model=list[MappingOverride])
def list_overrides(form_name: Optional[str] = None) -> list[MappingOverride]:
    """Return saved local mapping overrides (optionally filtered by form)."""

    try:
        return field_mapping_overrides.load_overrides(form_name)
    except field_mapping_overrides.MappingOverrideError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("", response_model=SaveOverrideResponse)
def create_override(body: MappingOverrideCreate) -> SaveOverrideResponse:
    """Create or update a mapping override. Sensitive force-fills are downgraded."""

    if body.action not in ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{body.action}'. Allowed: {sorted(ALLOWED_ACTIONS)}.",
        )

    warnings: list[str] = []
    action = body.action
    # Safety: an override can never force autofill of a sensitive field.
    if body.category in SENSITIVE_CATEGORIES and action == ACTION_FILL:
        action = ACTION_MANUAL_REVIEW
        warnings.append(
            "Sensitive category cannot be set to autofill; saved as manual review."
        )

    now = datetime.now(timezone.utc)
    override = MappingOverride(
        override_id=body.override_id or uuid.uuid4().hex,
        form_name=body.form_name,
        field_fingerprint=body.field_fingerprint,
        category=body.category,
        profile_path=body.profile_path,
        action=action,
        note=body.note,
        created_at=now,
        updated_at=now,
    )
    try:
        saved = field_mapping_overrides.save_override(override)
    except field_mapping_overrides.MappingOverrideError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SaveOverrideResponse(override=saved, warnings=warnings)


@router.delete("/{override_id}")
def remove_override(override_id: str) -> dict[str, object]:
    """Delete an override by id."""

    try:
        deleted = field_mapping_overrides.delete_override(override_id)
    except field_mapping_overrides.MappingOverrideError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Override '{override_id}' not found.")
    return {"deleted": True, "override_id": override_id}


@router.post("/apply-to-plan", response_model=FillPlan)
def apply_to_plan(body: ApplyToPlanRequest) -> FillPlan:
    """Re-analyze a local sample form with the saved overrides applied."""

    try:
        profile = profile_storage.load_profile()
    except profile_storage.ProfileStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="No saved profile found. Save a profile before applying overrides.",
        )

    try:
        form_path = sample_forms.resolve_sample_form(body.form_name)
    except sample_forms.UnknownSampleFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        return analyze_local_form(form_path, profile, form_name=body.form_name)
    except PlaywrightSetupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
