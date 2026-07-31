"""Read-only platform support endpoints (Phase 7).

Two questions the popup asks before it does anything:

- ``GET /platforms/supported`` - which platforms do you claim to support?
- ``POST /platforms/check-url`` - would you analyze this page?

Neither endpoint fetches the URL, resolves DNS, opens a browser, or touches disk.
Both are pure string evaluation against local rules, so calling them has no effect
on the page the user is looking at.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.models.platform import (
    CheckUrlRequest,
    CheckUrlResponse,
    SupportedPlatformsResponse,
)
from app.services.platform_allowlist import (
    detect_platform_from_url,
    get_approved_extra_domains,
    get_supported_platforms,
    is_url_allowed_for_phase7,
)

router = APIRouter(prefix="/platforms", tags=["platforms"])


@router.get("/supported", response_model=SupportedPlatformsResponse)
def supported_platforms() -> SupportedPlatformsResponse:
    """List every platform Phase 7 knows about and its current allow-list."""

    return SupportedPlatformsResponse(
        platforms=get_supported_platforms(),
        extra_approved_domains=get_approved_extra_domains(),
    )


@router.post("/check-url", response_model=CheckUrlResponse)
def check_url(body: CheckUrlRequest) -> CheckUrlResponse:
    """Report the detected platform and the authoritative safety decision.

    Returns 200 even when the page is blocked: this is an informational check the
    popup uses to decide what to show, not an authorization attempt. The blocking
    happens in ``POST /extension/analyze-real-page``.
    """

    return CheckUrlResponse(
        detection=detect_platform_from_url(body.page_url),
        safety=is_url_allowed_for_phase7(body.page_url),
    )
