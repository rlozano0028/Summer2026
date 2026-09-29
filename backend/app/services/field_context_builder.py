"""Build enriched :class:`FieldContext` objects from raw Phase 4 form fields.

This module is the first stage of the Phase 5 mapping pipeline. It takes the
raw :class:`~app.models.automation.FormField` produced by the detector and
produces a richer, normalized :class:`~app.models.field_mapping.FieldContext`
that the classifier/mapper can reason about without re-querying the DOM.

Design notes:
- ``field_text`` is a human-readable join of all the field's textual metadata.
- ``normalized_text`` is the lowercased, punctuation-normalized version used for
  keyword matching (snake_case, camelCase, hyphens, and extra whitespace are all
  flattened to single spaces).
- No private profile values are ever stored here; this layer only knows about
  the form's own metadata.
"""

from __future__ import annotations

import re

from app.models.automation import FormField
from app.models.field_mapping import FieldContext

# Splits camelCase / PascalCase boundaries (e.g. "firstName" -> "first Name").
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
# Any run of characters that is not a letter or digit becomes a space.
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_field_text(text: str) -> str:
    """Return a lowercased, punctuation-normalized form of ``text``.

    Underscores, hyphens, and other punctuation become spaces; camelCase
    boundaries are split; runs of whitespace collapse to one space. Empty or
    ``None``-like input yields an empty string.
    """

    if not text:
        return ""
    # Split camelCase before lowercasing so the boundary is detectable.
    spaced = _CAMEL_BOUNDARY.sub(" ", text)
    lowered = spaced.lower()
    cleaned = _NON_ALNUM.sub(" ", lowered)
    return _WHITESPACE.sub(" ", cleaned).strip()


def tokenize_field_text(text: str) -> list[str]:
    """Return the normalized tokens of ``text`` (deduplicated order preserved)."""

    normalized = normalize_field_text(text)
    if not normalized:
        return []
    tokens: list[str] = []
    for token in normalized.split(" "):
        if token and token not in tokens:
            tokens.append(token)
    return tokens


def _build_field_text(field: FormField) -> str:
    """Join all human-readable metadata into one display string."""

    parts = [
        field.label_text,
        field.placeholder,
        field.aria_label,
        field.name,
        field.id_attribute,
        field.autocomplete,
        field.nearby_text,
    ]
    text_parts = [p.strip() for p in parts if p and p.strip()]
    if field.options:
        option_text = " ".join(o.strip() for o in field.options if o and o.strip())
        if option_text:
            text_parts.append(option_text)
    return " | ".join(text_parts)


def build_field_context(field: FormField) -> FieldContext:
    """Convert a single raw :class:`FormField` into a rich :class:`FieldContext`."""

    field_text = _build_field_text(field)
    normalized_text = normalize_field_text(field_text)
    return FieldContext(
        field_id=field.field_id,
        selector=field.selector,
        tag_name=field.tag_name,
        input_type=field.input_type,
        field_text=field_text,
        normalized_text=normalized_text,
        label_text=field.label_text,
        nearby_text=field.nearby_text,
        placeholder=field.placeholder,
        name=field.name,
        id_attribute=field.id_attribute,
        aria_label=field.aria_label,
        autocomplete=field.autocomplete,
        options=list(field.options),
        required=field.required,
        visible=field.visible,
        disabled=field.disabled,
        readonly=field.readonly,
        is_file_upload=field.is_file_upload,
        is_submit_control=field.is_submit_control,
        is_textarea=field.is_textarea or field.tag_name == "textarea",
        is_select=field.is_select or field.tag_name == "select",
        is_checkbox=field.is_checkbox or field.input_type == "checkbox",
        is_radio=field.is_radio or field.input_type == "radio",
    )
