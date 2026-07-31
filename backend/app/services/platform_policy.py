"""The Phase 7 safety rules, in one place.

:mod:`app.services.platform_allowlist` decides *whether* a page may be analyzed.
This module decides what may happen once it is: what the user must acknowledge,
which decisions get downgraded, and which values are allowed out the door.

Four entry points:

- :func:`validate_real_platform_request` - refuses a real page without explicit
  user confirmation, and refuses anything the allow-list blocked.
- :func:`downgrade_unsupported_fields` - flips custom controls to
  ``manual_review`` so the extension is never asked to write to them.
- :func:`enforce_instruction_safety` - a final independent pass that nulls the
  value on any instruction that does not clearly qualify.
- :func:`build_real_platform_warnings` - the plain-language notes the popup shows.

:func:`enforce_instruction_safety` intentionally duplicates checks already made in
:mod:`app.services.extension_field_adapter`. It is the last thing that touches a
response, so a future change upstream cannot quietly widen what leaves the backend.

Nothing here reads or writes files, and no value is ever logged.
"""

from __future__ import annotations

from typing import Optional

from app.models.automation import (
    ACTION_FILL,
    ACTION_MANUAL_REVIEW,
    ACTION_SKIP,
    ACTION_SUGGEST,
    FillPlan,
)
from app.models.extension import (
    UNFILLABLE_FIELD_TYPES,
    ExtensionDetectedField,
    ExtensionFillInstruction,
)
from app.models.field_mapping import SENSITIVE_CATEGORIES
from app.models.platform import PLATFORM_LOCAL, PageSafetyDecision
from app.services.platform_allowlist import is_url_allowed_for_phase7

# Shown for every real page. Deliberately blunt: the user is about to let software
# type into a form they will submit under their own name.
REAL_PAGE_REVIEW_WARNING = (
    "Review every field on the page yourself before submitting. This tool never "
    "submits, never clicks Apply or Next, and can be wrong."
)


def validate_real_platform_request(
    page_url: str, user_confirmed_real_page: bool
) -> PageSafetyDecision:
    """Decide whether this specific request may proceed.

    Combines the URL allow-list with the user's confirmation. A page that is
    allowed *in principle* is still refused when confirmation is required and the
    request does not carry it, so the confirmation cannot be skipped by calling the
    API directly.
    """

    decision = is_url_allowed_for_phase7(page_url)

    if not decision.allowed:
        return decision

    if decision.requires_user_confirmation and not user_confirmed_real_page:
        blocked = (
            "This is a real application page. Confirm in the extension that you "
            "want it analyzed before continuing."
        )
        return PageSafetyDecision(
            allowed=False,
            platform_id=decision.platform_id,
            reason=blocked,
            warnings=decision.warnings,
            requires_user_confirmation=True,
            blocked_reason=blocked,
        )

    return decision


def downgrade_unsupported_fields(
    fill_plan: FillPlan, fields: list[ExtensionDetectedField]
) -> tuple[FillPlan, int]:
    """Route custom controls to manual review and recount the plan.

    A custom control is anything the extension cannot write to deterministically:
    an ARIA combobox, a contenteditable region, a framework-owned dropdown. The
    mapping engine has no idea these exist, so we correct its output here instead
    of teaching it about DOM quirks.

    Returns:
        A copy of the plan with corrected actions and counts, plus how many of its
        decisions concern custom controls. That count includes fields the mapper
        had already routed to manual review, because it is reported to the user as
        "how much of this form you must fill yourself", not as an internal edit
        count. The input plan is never mutated.
    """

    unsupported = {
        field.field_id: field for field in fields if field.is_custom_control
    }
    if not unsupported:
        return fill_plan, 0

    plan = fill_plan.model_copy(deep=True)
    unsupported_count = 0
    for mapping in plan.mappings:
        field = unsupported.get(mapping.field_id)
        if field is None:
            continue
        unsupported_count += 1
        detail = field.unsupported_reason or "custom control the extension will not modify"
        mapping.action = ACTION_MANUAL_REVIEW
        mapping.reason = f"Manual review: {detail}."
        if "Unsupported control type on this platform." not in mapping.warnings:
            mapping.warnings = [
                *mapping.warnings,
                "Unsupported control type on this platform.",
            ]

    if unsupported_count:
        _recount(plan)
        plan.warnings = [
            *plan.warnings,
            f"{unsupported_count} field(s) use controls this extension will not "
            "modify; fill them yourself.",
        ]
    return plan, unsupported_count


def _recount(plan: FillPlan) -> None:
    """Recompute the plan's summary counts after actions changed."""

    actions = [mapping.action for mapping in plan.mappings]
    plan.fill_count = actions.count(ACTION_FILL)
    plan.suggest_count = actions.count(ACTION_SUGGEST)
    plan.manual_review_count = actions.count(ACTION_MANUAL_REVIEW)
    plan.skip_count = actions.count(ACTION_SKIP)


def enforce_instruction_safety(
    instructions: list[ExtensionFillInstruction],
    fields: Optional[list[ExtensionDetectedField]] = None,
) -> tuple[list[ExtensionFillInstruction], list[str]]:
    """Strip any value that is not provably safe to send.

    Independent of how the instructions were produced. A value survives only when
    all of the following hold: the action is ``fill``, the category is not
    sensitive, the field type is a plain text, textarea, or select control, and the
    matching detected field (when supplied) is visible, enabled, editable, not a
    password, not a file input, not a submit control, and not a custom control.

    Returns:
        New instruction objects, plus one warning per stripped value naming the
        field id and the rule that stripped it. Warnings never contain values.
    """

    fields_by_id = {field.field_id: field for field in (fields or [])}
    cleaned: list[ExtensionFillInstruction] = []
    warnings: list[str] = []

    for instruction in instructions:
        reason = _unsafe_reason(instruction, fields_by_id.get(instruction.field_id))
        if reason is None or instruction.value is None:
            cleaned.append(instruction.model_copy(deep=True))
            continue
        cleaned.append(instruction.model_copy(deep=True, update={"value": None}))
        warnings.append(
            f"Withheld the value for '{instruction.field_id}': {reason}."
        )

    return cleaned, warnings


def _unsafe_reason(
    instruction: ExtensionFillInstruction, field: Optional[ExtensionDetectedField]
) -> Optional[str]:
    """Why this instruction may not carry a value, or None if it may."""

    if instruction.action != ACTION_FILL:
        return f"the plan action is '{instruction.action}', not 'fill'"
    if instruction.category and instruction.category in SENSITIVE_CATEGORIES:
        return f"'{instruction.category}' is a sensitive category"
    if instruction.field_type in UNFILLABLE_FIELD_TYPES:
        return f"'{instruction.field_type}' controls are never filled automatically"
    if field is None:
        return None
    if (field.input_type or "").strip().lower() == "password":
        return "it is a password input"
    if field.is_file_upload:
        return "it is a file upload"
    if field.is_submit_control:
        return "it is a submit control"
    if field.is_custom_control:
        return "it is a custom control the extension will not modify"
    if field.disabled or field.readonly:
        return "the field is disabled or read-only"
    if not field.visible:
        return "the field is not visible"
    return None


def build_real_platform_warnings(
    safety: PageSafetyDecision,
    fields: list[ExtensionDetectedField],
    unsupported_count: int = 0,
) -> list[str]:
    """The notes the popup shows above a real-page fill plan.

    Ordered from page-level to field-level so the most important context is read
    first. Duplicates are removed while preserving order.
    """

    warnings: list[str] = []
    if safety.platform_id != PLATFORM_LOCAL:
        warnings.extend(safety.warnings)
        warnings.append(REAL_PAGE_REVIEW_WARNING)

    if not fields:
        warnings.append(
            "No fields were detected. The form may be inside an iframe, or may not "
            "have loaded yet."
        )

    if unsupported_count:
        warnings.append(
            f"{unsupported_count} field(s) use custom controls and were left for "
            "manual review."
        )

    sensitive = sum(
        1
        for field in fields
        if field.is_file_upload or (field.input_type or "").lower() == "file"
    )
    if sensitive:
        warnings.append(
            f"{sensitive} file upload(s) detected. Attach files yourself; the "
            "extension cannot and will not."
        )

    deduped: list[str] = []
    for warning in warnings:
        if warning not in deduped:
            deduped.append(warning)
    return deduped
