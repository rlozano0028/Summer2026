"""Pydantic models for the Chrome-extension integration (Phase 6).

Phase 6 lets a local Chrome extension send *field metadata only* from the page it
is on, receive a Phase 5 fill plan, and apply only the safe ``action="fill"``
decisions after the user reviews them.

These models are deliberately separate from the Phase 4/5 automation models so
that extension traffic never changes the behaviour of the Playwright prototype.
:class:`ExtensionDetectedField` mirrors :class:`~app.models.automation.FormField`
closely enough that :mod:`app.services.extension_field_adapter` can convert it
without duplicating any mapping logic.

Privacy rules enforced across this module:

- The extension never sends element values, page HTML, or page text.
- ``value_preview`` is always the redacted preview produced by Phase 5.
- :class:`ExtensionFillInstruction` is a **transient** wire model. Its ``value``
  may hold a real private profile value, but only for ``action="fill"`` on a
  non-sensitive field. It must never be written to disk, logged, or included in
  an automation report.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.automation import FillPlan

# Local development origins the extension is allowed to operate on in Phase 6.
# Anything else is rejected: Phase 6 explicitly does not automate real job sites.
ALLOWED_PAGE_ORIGINS: tuple[str, ...] = (
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
)

# Values used for ``ExtensionFillInstruction.field_type`` so the content script
# knows how to apply a value without re-inspecting the element's semantics.
FIELD_TYPE_TEXT = "text"
FIELD_TYPE_TEXTAREA = "textarea"
FIELD_TYPE_SELECT = "select"
FIELD_TYPE_CHECKBOX = "checkbox"
FIELD_TYPE_RADIO = "radio"
FIELD_TYPE_FILE = "file"
# Phase 7: submit / apply / next controls are named explicitly so the platform
# policy can reject them by type rather than inferring it from the action.
FIELD_TYPE_SUBMIT = "submit"
FIELD_TYPE_OTHER = "other"

# Field types the extension will never write a value into.
UNFILLABLE_FIELD_TYPES: frozenset[str] = frozenset(
    {
        FIELD_TYPE_FILE,
        FIELD_TYPE_CHECKBOX,
        FIELD_TYPE_RADIO,
        FIELD_TYPE_SUBMIT,
        FIELD_TYPE_OTHER,
    }
)


class ExtensionDetectedField(BaseModel):
    """Metadata for one field the content script found on the current page.

    Mirrors :class:`~app.models.automation.FormField`. ``selector`` is a CSS
    selector the content script generated and can resolve again later; it is the
    only thing tying an instruction back to a DOM element.

    Note: the content script never populates a value here. Password inputs are
    skipped during detection and dropped again server-side as a safety net.
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
    is_textarea: bool = False
    is_select: bool = False
    is_checkbox: bool = False
    is_radio: bool = False
    # Phase 7 additions, both defaulted so Phase 6 request bodies validate unchanged.
    # Real application pages use ARIA comboboxes, contenteditable divs, and custom
    # dropdowns whose state lives in framework code. The extension refuses to write
    # to them, so detection flags them here and they route to manual review.
    is_custom_control: bool = False
    unsupported_reason: Optional[str] = None


class ExtensionAnalyzeRequest(BaseModel):
    """Body for ``POST /extension/analyze-page``.

    This is metadata-only analysis. The backend does not open ``page_url``, does
    not fetch it, and does not drive a browser: ``page_url`` is used purely for
    the local allow-list check and for labelling the resulting plan.
    """

    page_url: str
    page_title: Optional[str] = None
    # Optional label used to look up local mapping overrides (Phase 5).
    form_name: Optional[str] = None
    fields: list[ExtensionDetectedField] = Field(default_factory=list)


class ExtensionFillInstruction(BaseModel):
    """A single transient instruction for the content script.

    ``value`` holds a real profile value **only** when ``action == "fill"`` on a
    safe, non-sensitive, fillable field. It is ``None`` for ``suggest``,
    ``manual_review``, and ``skip``, for sensitive/legal fields, for missing
    values, for file uploads, and for anything unsupported.

    Never persist this model and never log ``value``.
    """

    field_id: str
    selector: str
    action: str
    value: Optional[str] = None
    value_preview: Optional[str] = None
    field_type: Optional[str] = None
    category: Optional[str] = None
    reason: str = ""


class ExtensionAnalyzeResponse(BaseModel):
    """Response for ``POST /extension/analyze-page``.

    ``fill_plan`` carries redacted previews only and is what the popup shows in
    its review table. ``instructions`` is the transient companion the popup hands
    straight to the content script without storing it.
    """

    page_url: str
    page_title: Optional[str] = None
    profile_review_status: Optional[bool] = None
    warnings: list[str] = Field(default_factory=list)
    fill_plan: FillPlan
    instructions: list[ExtensionFillInstruction] = Field(default_factory=list)


class ExtensionHealthResponse(BaseModel):
    """Response for ``GET /extension/health``."""

    ok: bool = True
    backend: str
    profile_exists: bool = False
    profile_needs_review: Optional[bool] = None
    message: str = ""


class ExtensionValidatePageRequest(BaseModel):
    """Body for ``POST /extension/validate-page``."""

    page_url: str


class ExtensionValidatePageResponse(BaseModel):
    """Whether a page URL is allowed for Phase 6, plus the allow-list."""

    page_url: str
    allowed: bool
    reason: str = ""
    allowed_origins: list[str] = Field(default_factory=list)
