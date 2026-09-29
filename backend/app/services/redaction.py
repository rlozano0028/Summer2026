"""Redaction helpers for previews stored in fill plans and automation reports.

Phase 5 never stores a full private value in a plan or report. These helpers
produce short, masked previews that are safe to display in the UI and to write
to a local JSON report:

- :func:`redact_email` - ``ada@example.com`` -> ``a***@example.com``
- :func:`redact_phone` - ``555-123-4567`` -> ``***4567`` style masking
- :func:`shorten_value` - truncate any long string to a max length
- :func:`redact_profile_value` - pick the right strategy from the profile path

The full (un-redacted) value is only ever resolved at fill time by the runner
and is never persisted.
"""

from __future__ import annotations

from typing import Optional

# Default maximum length for a previewed value.
DEFAULT_MAX_LENGTH = 80

_ELLIPSIS = "\u2026"


def shorten_value(value: str, max_length: int = DEFAULT_MAX_LENGTH) -> str:
    """Truncate ``value`` to ``max_length`` characters with an ellipsis."""

    text = (value or "").strip()
    if max_length <= 0 or len(text) <= max_length:
        return text
    # Reserve one character for the ellipsis.
    return f"{text[: max_length - 1]}{_ELLIPSIS}"


def redact_email(value: str) -> str:
    """Mask the local part of an email: ``ada@example.com`` -> ``a***@example.com``.

    If the value does not look like an email, fall back to :func:`shorten_value`.
    """

    text = (value or "").strip()
    if "@" not in text:
        return shorten_value(text)
    local, _, domain = text.partition("@")
    if not local:
        return f"***@{domain}"
    return f"{local[:1]}***@{domain}"


def redact_phone(value: str) -> str:
    """Mask a phone number, keeping only the last 2-4 digits visible."""

    text = (value or "").strip()
    digits = [c for c in text if c.isdigit()]
    if not digits:
        return shorten_value(text)
    visible = "".join(digits[-4:]) if len(digits) >= 4 else "".join(digits[-2:])
    return f"***{visible}"


def _looks_like_email(value: str) -> bool:
    return "@" in value


def _looks_like_phone(value: str) -> bool:
    # Only digits and phone punctuation, so a URL or ID that happens to contain
    # digits (e.g. a LinkedIn slug) is not masked as a phone number.
    return sum(c.isdigit() for c in value) >= 5 and all(
        c.isdigit() or c in " +-().x" for c in value
    )


def redact_profile_value(profile_path: Optional[str], value: Optional[str]) -> Optional[str]:
    """Return a redacted preview appropriate for ``profile_path``/``value``.

    Strategy:
    - email paths or email-looking values -> :func:`redact_email`
    - phone paths or phone-looking values -> :func:`redact_phone`
    - everything else -> :func:`shorten_value`
    """

    if value is None:
        return None
    text = value.strip()
    if not text:
        return ""

    path = (profile_path or "").lower()
    if "email" in path or _looks_like_email(text):
        return redact_email(text)
    if "phone" in path or _looks_like_phone(text):
        return redact_phone(text)
    return shorten_value(text)
