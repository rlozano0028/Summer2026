"""Adapt Chrome-extension field metadata onto the Phase 5 mapping engine (Phase 6).

This module is the only bridge between extension traffic and the existing
mapping engine. It deliberately contains no classification, confidence, or
sensitivity logic: every decision comes from
:func:`app.services.field_mapper.build_fill_plan`, unchanged from Phase 5.

Two responsibilities:

1. :func:`convert_extension_fields_to_form_fields` - turn
   :class:`ExtensionDetectedField` objects into :class:`FormField` objects the
   mapper already understands.
2. :func:`build_extension_response` - pair the resulting plan with transient
   fill instructions, attaching a real value only where it is provably safe.

Privacy: nothing here writes to disk and nothing logs a resolved value.
"""

from __future__ import annotations

from typing import Optional

from app.models.automation import ACTION_FILL, FillPlan, FieldMapping, FormField
from app.models.candidate_profile import CandidateProfile
from app.models.extension import (
    FIELD_TYPE_CHECKBOX,
    FIELD_TYPE_FILE,
    FIELD_TYPE_OTHER,
    FIELD_TYPE_RADIO,
    FIELD_TYPE_SELECT,
    FIELD_TYPE_SUBMIT,
    FIELD_TYPE_TEXT,
    FIELD_TYPE_TEXTAREA,
    ExtensionAnalyzeResponse,
    ExtensionDetectedField,
    ExtensionFillInstruction,
)
from app.models.field_mapping import SENSITIVE_CATEGORIES
from app.services.field_value_resolver import resolve_raw_value

# Input types we never fill from the extension, regardless of the plan's action.
# Passwords are dropped before mapping; the rest are belt-and-braces guards.
UNFILLABLE_INPUT_TYPES: frozenset[str] = frozenset(
    {"password", "file", "submit", "button", "reset", "image", "hidden"}
)


def _is_password(field: ExtensionDetectedField) -> bool:
    return (field.input_type or "").strip().lower() == "password"


def convert_extension_fields_to_form_fields(
    fields: list[ExtensionDetectedField],
) -> tuple[list[FormField], list[str]]:
    """Convert extension fields into Phase 5 :class:`FormField` inputs.

    Password inputs are dropped entirely rather than mapped, so they can never
    appear in a plan or an instruction. The content script already skips them;
    this is the server-side safety net.

    Returns:
        The converted fields, plus the ``field_id`` values that were dropped.
    """

    converted: list[FormField] = []
    dropped: list[str] = []
    for field in fields:
        if _is_password(field):
            dropped.append(field.field_id)
            continue
        converted.append(
            FormField(
                field_id=field.field_id,
                selector=field.selector,
                tag_name=field.tag_name,
                input_type=field.input_type,
                name=field.name,
                id_attribute=field.id_attribute,
                placeholder=field.placeholder,
                aria_label=field.aria_label,
                label_text=field.label_text,
                nearby_text=field.nearby_text,
                autocomplete=field.autocomplete,
                required=field.required,
                visible=field.visible,
                disabled=field.disabled,
                readonly=field.readonly,
                options=list(field.options),
                is_file_upload=field.is_file_upload,
                is_submit_control=field.is_submit_control,
                is_textarea=field.is_textarea,
                is_select=field.is_select,
                is_checkbox=field.is_checkbox,
                is_radio=field.is_radio,
            )
        )
    return converted, dropped


def _field_type_for(field: Optional[ExtensionDetectedField]) -> str:
    """Classify how the content script should apply a value to this element."""

    if field is None:
        return FIELD_TYPE_OTHER
    if field.is_file_upload or (field.input_type or "").lower() == "file":
        return FIELD_TYPE_FILE
    # Named before the tag checks so a <button type="submit"> or <input type="submit">
    # is reported as a submit control rather than as generic text.
    if field.is_submit_control or (field.input_type or "").lower() in {"submit", "image"}:
        return FIELD_TYPE_SUBMIT
    if field.is_select or field.tag_name.lower() == "select":
        return FIELD_TYPE_SELECT
    if field.is_checkbox:
        return FIELD_TYPE_CHECKBOX
    if field.is_radio:
        return FIELD_TYPE_RADIO
    if field.is_textarea or field.tag_name.lower() == "textarea":
        return FIELD_TYPE_TEXTAREA
    if field.tag_name.lower() == "input":
        return FIELD_TYPE_TEXT
    return FIELD_TYPE_OTHER


def _may_carry_value(
    mapping: FieldMapping, field: Optional[ExtensionDetectedField]
) -> bool:
    """Return True only when it is provably safe to send a real value.

    Every condition must hold. Any doubt means the instruction goes out with
    ``value=None`` and the user fills the field by hand.
    """

    if mapping.action != ACTION_FILL:
        return False
    if mapping.sensitive or mapping.missing_value:
        return False
    if mapping.category in SENSITIVE_CATEGORIES:
        return False
    if not mapping.profile_path:
        return False
    if field is None:
        # The mapping has no matching detected field; we cannot verify it is safe.
        return False
    if _is_password(field) or field.is_file_upload or field.is_submit_control:
        return False
    # Phase 7: custom controls (ARIA comboboxes, contenteditable, framework-owned
    # dropdowns) cannot be filled reliably, so we never send them a value.
    if field.is_custom_control:
        return False
    if field.disabled or field.readonly or not field.visible:
        return False
    if (field.input_type or "").strip().lower() in UNFILLABLE_INPUT_TYPES:
        return False
    # Checkboxes and radios are never toggled from the extension in Phase 6.
    if field.is_checkbox or field.is_radio:
        return False
    return True


def build_fill_instructions(
    fill_plan: FillPlan,
    profile: CandidateProfile,
    fields: list[ExtensionDetectedField],
) -> tuple[list[ExtensionFillInstruction], list[str]]:
    """Turn plan decisions into transient instructions, gating every value.

    Decisions are taken verbatim from ``fill_plan``; this only decides whether each
    one may carry a real value and resolves it when so.

    Extracted in Phase 7 so ``/extension/analyze-real-page`` reuses the identical
    gate rather than reimplementing it.

    Returns:
        The instructions, plus warnings about values that failed to resolve.
    """

    fields_by_id = {field.field_id: field for field in fields}
    warnings: list[str] = []

    instructions: list[ExtensionFillInstruction] = []
    for mapping in fill_plan.mappings:
        field = fields_by_id.get(mapping.field_id)
        value: Optional[str] = None
        if _may_carry_value(mapping, field):
            value = resolve_raw_value(profile, mapping.profile_path)
            if value is None:
                # Plan said fill but the profile no longer resolves; degrade safely.
                warnings.append(
                    f"No profile value resolved for '{mapping.field_id}'; left for manual entry."
                )
        instructions.append(
            ExtensionFillInstruction(
                field_id=mapping.field_id,
                selector=mapping.selector,
                action=mapping.action,
                value=value,
                value_preview=mapping.value_preview,
                field_type=_field_type_for(field),
                category=mapping.category,
                reason=mapping.reason,
            )
        )
    return instructions, warnings


def build_extension_response(
    page_url: str,
    page_title: Optional[str],
    fill_plan: FillPlan,
    profile: CandidateProfile,
    fields: list[ExtensionDetectedField],
    warnings: Optional[list[str]] = None,
) -> ExtensionAnalyzeResponse:
    """Pair a Phase 5 plan with transient, gated fill instructions."""

    instructions, resolve_warnings = build_fill_instructions(fill_plan, profile, fields)
    response_warnings = [*(warnings or []), *resolve_warnings]

    return ExtensionAnalyzeResponse(
        page_url=page_url,
        page_title=page_title,
        profile_review_status=profile.metadata.needs_review,
        warnings=response_warnings,
        fill_plan=fill_plan,
        instructions=instructions,
    )
