"""Shared helpers for Playwright-dependent tests.

These tests must skip cleanly (not fail) when the Chromium browser binary is not
installed, since CI or a fresh checkout may not have run
``python -m playwright install chromium`` yet.
"""

from __future__ import annotations

import functools

SETUP_HINT = (
    "Chromium not available. Install with: python -m playwright install chromium"
)


@functools.lru_cache(maxsize=1)
def chromium_available() -> bool:
    """Return True if Playwright can launch headless Chromium."""

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:  # noqa: BLE001 - missing binary or launch failure.
        return False
