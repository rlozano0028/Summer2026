"""Pydantic models for the browser-automation prototype (Phase 4).

These models describe what Playwright detects on a local sample form, how each
detected field maps to the reviewed :class:`CandidateProfile`, and the result of
an autofill run.

Privacy notes:
- ``FieldMapping.value_preview`` is always redacted/shortened. Full sensitive
  values (emails, phone numbers, etc.) must never be stored in a plan or report.
- Sensitive / legal fields are tracked explicitly with ``sensitive=True`` and are
  never autofilled in this phase.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.field_mapping import MatchEvidence

# Allowed values for ``FieldMapping.action``. Kept as a module constant so the
# mapper, runner, and tests share one source of truth.
ACTION_FILL = "fill"
ACTION_SUGGEST = "suggest"
ACTION_MANUAL_REVIEW = "manual_review"
ACTION_SKIP = "skip"
ALLOWED_ACTIONS = frozenset({ACTION_FILL, ACTION_SUGGEST, ACTION_MANUAL_REVIEW, ACTION_SKIP})


class FormField(BaseModel):
    """Metadata about a single field detected on a form.

    ``field_id`` is a stable identifier assigned during detection (used to
    correlate a field with its mapping). ``selector`` is a CSS selector
    Playwright can use to locate the element.
    """

    field_id: str
    selector: str
    tag_name: str
    input_type: Optional[str] = None
    name: Optional[str] = None
    id_attribute: Optional[str] = None
    placeholder: Optional[str] = None
    aria_label: Optional[str] = None
    label_text: Optional[str] = None
    nearby_text: Optional[str] = None
    autocomplete: Optional[str] = None
    required: bool = False
    visible: bool = True
    disabled: bool = False
    readonly: bool = False
    options: list[str] = Field(default_factory=list)
    is_file_upload: bool = False
    is_submit_control: bool = False
    # Phase 5: convenience flags so higher layers don't re-query the DOM.
    is_textarea: bool = False
    is_select: bool = False
    is_checkbox: bool = False
    is_radio: bool = False


class FieldMapping(BaseModel):
    """A deterministic decision about how to handle one detected field.

    Phase 5 enriches this model with ``category``, ``evidence``, and
    ``warnings`` while keeping every Phase 4 field intact for backward
    compatibility. It remains the model carried inside :class:`FillPlan`.
    """

    field_id: str
    selector: str
    profile_path: Optional[str] = None
    # Redacted / shortened preview of the value (never the full sensitive value).
    value_preview: Optional[str] = None
    confidence: float = 0.0
    action: str = ACTION_SKIP
    reason: str = ""
    sensitive: bool = False
    missing_value: bool = False
    # Phase 5 additions (default-safe for backward compatibility).
    category: str = "unknown"
    evidence: list[MatchEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # Stable fingerprint of non-private field metadata, used to attach overrides.
    field_fingerprint: str = ""


class FillPlan(BaseModel):
    """The full set of mapping decisions for a form, plus summary counts."""

    form_name: str
    form_url: str
    generated_at: datetime
    mappings: list[FieldMapping] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    manual_review_count: int = 0
    fill_count: int = 0
    suggest_count: int = 0
    skip_count: int = 0


class AutofillResult(BaseModel):
    """The outcome of actually running (or dry-running) autofill on a form."""

    form_name: str
    form_url: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    filled_fields: list[str] = Field(default_factory=list)
    suggested_fields: list[str] = Field(default_factory=list)
    manual_review_fields: list[str] = Field(default_factory=list)
    skipped_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    report_path: Optional[str] = None
    success: bool = False
    # Phase 5: the enriched plan (redacted previews only) for explainable reports.
    plan: Optional[FillPlan] = None


class AutomationRequest(BaseModel):
    """Options controlling an autofill run.

    ``resume_file_path`` is optional. File-upload fields stay ``manual_review``
    unless the user explicitly provides a local resume path here.
    """

    form_name: str
    headless: bool = False
    dry_run: bool = False
    resume_file_path: Optional[str] = None
    keep_browser_open: bool = False
