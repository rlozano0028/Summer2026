"""Tests for the preview redaction helpers."""

from __future__ import annotations

from app.services.redaction import (
    redact_email,
    redact_phone,
    redact_profile_value,
    shorten_value,
)


def test_email_keeps_only_first_letter_and_domain() -> None:
    assert redact_email("ada@example.com") == "a***@example.com"


def test_phone_keeps_last_four_digits() -> None:
    assert redact_phone("(555) 123-4567") == "***4567"


def test_long_values_are_shortened() -> None:
    assert len(shorten_value("x" * 200)) == 80


def test_profile_value_picks_strategy_from_path() -> None:
    assert redact_profile_value("identity.email", "ada@example.com") == "a***@example.com"
    assert redact_profile_value("identity.phone", "555-123-4567") == "***4567"
    assert redact_profile_value("identity.city", "London") == "London"
    assert redact_profile_value("identity.city", None) is None


def test_url_with_digits_is_not_treated_as_a_phone_number() -> None:
    url = "linkedin.com/in/ada-lovelace-043146293/"
    assert redact_profile_value("links.linkedin", url) == url


def test_unlabelled_phone_looking_value_is_still_masked() -> None:
    assert redact_profile_value("custom.contact", "+1 555 123 4567") == "***4567"
