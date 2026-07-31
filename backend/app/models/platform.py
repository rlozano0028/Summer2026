"""Pydantic models for controlled real-platform support (Phase 7).

Phase 6 restricted the Chrome extension to loopback development pages. Phase 7
lets the user point it at a real application page they opened themselves, but only
on an explicitly supported platform and only after they confirm what will happen.

The models here describe three separate concerns, kept apart on purpose:

- :class:`SupportedPlatform` - static facts about a platform we claim to support.
- :class:`PlatformDetection` - what we think the current page *is*.
- :class:`PageSafetyDecision` - whether we are willing to analyze it.

Detection is advisory; the safety decision is authoritative. Keeping them separate
means a confident detection can still be refused, which is the behaviour we want
when a platform is known but disabled or too risky.

Every decision fails closed: an unknown, ambiguous, or unparseable URL is blocked
rather than treated as generic.

Privacy: nothing here holds page content or profile values. Fill values travel
only in the transient :class:`~app.models.extension.ExtensionFillInstruction`
objects reused from Phase 6.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.automation import FillPlan
from app.models.extension import ExtensionDetectedField, ExtensionFillInstruction

# Risk levels for a platform, ordered least to most risky.
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
ALLOWED_RISK_LEVELS = frozenset({RISK_LOW, RISK_MEDIUM, RISK_HIGH})

# Platform identifiers. ``local`` preserves the Phase 6 behaviour exactly;
# ``unsupported`` is the fail-closed result for anything we do not recognize.
PLATFORM_LOCAL = "local"
PLATFORM_GENERIC = "generic"
PLATFORM_GREENHOUSE = "greenhouse"
PLATFORM_LEVER = "lever"
PLATFORM_ASHBY = "ashby"
PLATFORM_WORKDAY = "workday"
PLATFORM_SMARTRECRUITERS = "smartrecruiters"
PLATFORM_UNSUPPORTED = "unsupported"


class SupportedPlatform(BaseModel):
    """Static description of a platform the extension claims to support.

    ``default_allowed_domains`` lists host patterns, where a leading dot means
    "this host or any subdomain of it" (``.greenhouse.io``). Matching is always on
    host boundaries, never substrings, so ``greenhouse.io.example.com`` does not
    match.
    """

    platform_id: str
    display_name: str
    enabled: bool = True
    default_allowed_domains: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    supports_standard_inputs: bool = True
    supports_custom_selects: bool = False
    supports_iframes: bool = False
    risk_level: str = RISK_HIGH


class PlatformDetection(BaseModel):
    """What platform we believe a page belongs to, and why.

    ``matched_by`` records the evidence (``url:host-suffix``, ``page-signal:...``)
    so a surprising result can be explained rather than guessed at. ``allowed``
    mirrors the safety decision for convenience; the authoritative answer is in
    :class:`PageSafetyDecision`.
    """

    platform_id: str = PLATFORM_UNSUPPORTED
    display_name: str = "Unsupported page"
    confidence: float = 0.0
    matched_by: list[str] = Field(default_factory=list)
    page_url: str = ""
    allowed: bool = False
    reason: str = ""
    warnings: list[str] = Field(default_factory=list)


class PageSafetyDecision(BaseModel):
    """Whether Phase 7 will analyze a page, and what the user must acknowledge.

    ``requires_user_confirmation`` is True for every non-local page. The route
    refuses to analyze such a page unless the request carries
    ``user_confirmed_real_page=True``.
    """

    allowed: bool = False
    platform_id: Optional[str] = None
    reason: str = ""
    warnings: list[str] = Field(default_factory=list)
    requires_user_confirmation: bool = False
    blocked_reason: Optional[str] = None


class RealPlatformAnalyzeRequest(BaseModel):
    """Body for ``POST /extension/analyze-real-page``.

    ``platform_id`` and ``platform_confidence`` are the *extension's* opinion,
    derived from page signals the backend cannot see. They are treated as hints
    only: the backend re-derives the platform from the URL and never widens access
    based on what the caller claims.

    ``user_confirmed_real_page`` must be True for any non-local page. It records
    that the user ticked the confirmation box in the popup.
    """

    page_url: str
    page_title: Optional[str] = None
    platform_id: Optional[str] = None
    platform_confidence: Optional[float] = None
    user_confirmed_real_page: bool = False
    fields: list[ExtensionDetectedField] = Field(default_factory=list)


class RealPlatformAnalyzeResponse(BaseModel):
    """Response for ``POST /extension/analyze-real-page``.

    Same two-part shape as Phase 6: ``fill_plan`` carries redacted previews for
    display, and ``instructions`` carries transient values for the content script -
    only ever for a safe ``action="fill"`` field. ``unsupported_count`` reports how
    many fields were downgraded because they are custom controls the extension will
    not touch.
    """

    page_url: str
    page_title: Optional[str] = None
    platform: Optional[PlatformDetection] = None
    safety: PageSafetyDecision
    warnings: list[str] = Field(default_factory=list)
    fill_plan: FillPlan
    instructions: list[ExtensionFillInstruction] = Field(default_factory=list)
    unsupported_count: int = 0


class SupportedPlatformsResponse(BaseModel):
    """Response for ``GET /platforms/supported``."""

    platforms: list[SupportedPlatform] = Field(default_factory=list)
    # Domains a developer added locally via PHASE7_APPROVED_DOMAINS.
    extra_approved_domains: list[str] = Field(default_factory=list)


class CheckUrlRequest(BaseModel):
    """Body for ``POST /platforms/check-url``. The URL is never fetched."""

    page_url: str


class CheckUrlResponse(BaseModel):
    """Detection plus the authoritative safety decision for one URL."""

    detection: PlatformDetection
    safety: PageSafetyDecision
