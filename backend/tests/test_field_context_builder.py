"""Tests for the Phase 5 field context builder."""

from __future__ import annotations

from app.models.automation import FormField
from app.services.field_context_builder import (
    build_field_context,
    normalize_field_text,
    tokenize_field_text,
)


def _field(**kwargs) -> FormField:
    defaults = dict(field_id="f0", selector="#f0", tag_name="input", input_type="text")
    defaults.update(kwargs)
    return FormField(**defaults)


def test_normalizes_snake_case() -> None:
    assert normalize_field_text("first_name") == "first name"


def test_normalizes_camel_case() -> None:
    assert normalize_field_text("firstName") == "first name"
    assert normalize_field_text("linkedInUrl") == "linked in url"


def test_normalizes_hyphenated_and_spaced() -> None:
    assert normalize_field_text("given-name") == "given name"
    assert normalize_field_text("  First   Name ") == "first name"


def test_tokenize_dedupes_preserving_order() -> None:
    assert tokenize_field_text("First name first") == ["first", "name"]


def test_combines_all_metadata_into_field_text() -> None:
    field = _field(
        label_text="First name",
        placeholder="Ada",
        name="first_name",
        id_attribute="first-name",
        aria_label="First name",
        autocomplete="given-name",
        nearby_text="Your legal first name",
        options=["a", "b"],
    )
    context = build_field_context(field)
    # field_text carries the human-readable pieces.
    assert "First name" in context.field_text
    assert "Ada" in context.field_text
    # normalized_text is lowercased and punctuation-flattened.
    assert "first name" in context.normalized_text
    assert "given name" in context.normalized_text


def test_handles_missing_metadata_gracefully() -> None:
    context = build_field_context(_field())
    assert context.field_text == ""
    assert context.normalized_text == ""
    assert context.field_id == "f0"


def test_sets_type_flags_from_tag_and_type() -> None:
    textarea = build_field_context(_field(tag_name="textarea", input_type=None))
    assert textarea.is_textarea is True
    select = build_field_context(_field(tag_name="select", input_type=None))
    assert select.is_select is True
    checkbox = build_field_context(_field(input_type="checkbox"))
    assert checkbox.is_checkbox is True
    radio = build_field_context(_field(input_type="radio"))
    assert radio.is_radio is True
