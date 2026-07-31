"""Which pages Phase 7 is willing to look at, and what platform they belong to.

This module answers two questions about a URL *string*. It never fetches the URL,
never resolves DNS, and never makes any network call:

1. :func:`detect_platform_from_url` - which platform does this look like?
2. :func:`is_url_allowed_for_phase7` - are we willing to analyze it at all?

Detection is advisory. The safety decision is authoritative, and it fails closed:
anything not explicitly recognized is blocked rather than treated as generic.

Host matching rules, chosen so a lookalike domain cannot slip through:

- A pattern with a leading dot (``.greenhouse.io``) matches that host or any
  subdomain of it, on label boundaries only.
- Substring matching is never used, so ``greenhouse.io.evil.example.com`` and
  ``notgreenhouse.io`` both fail.
- Real platforms must be served over ``https``. Only loopback development pages
  may use ``http``.

Company-hosted application pages (the ``generic`` platform) are deliberately not
matched by any pattern. A developer opts a specific host in via the
``PHASE7_APPROVED_DOMAINS`` environment variable, which requires a restart. That
friction is intentional: adding a real domain should be a deliberate act, not a
click.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit

from app.models.extension import ALLOWED_PAGE_ORIGINS
from app.models.platform import (
    PLATFORM_ASHBY,
    PLATFORM_GENERIC,
    PLATFORM_GREENHOUSE,
    PLATFORM_LEVER,
    PLATFORM_LOCAL,
    PLATFORM_SMARTRECRUITERS,
    PLATFORM_UNSUPPORTED,
    PLATFORM_WORKDAY,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    PageSafetyDecision,
    PlatformDetection,
    SupportedPlatform,
)

APPROVED_DOMAINS_ENV_VAR = "PHASE7_APPROVED_DOMAINS"

# Loopback hosts, derived from the Phase 6 allow-list so the two cannot drift.
_LOCAL_ORIGINS = frozenset(ALLOWED_PAGE_ORIGINS)


@dataclass(frozen=True)
class _PlatformRule:
    """A platform plus the host patterns that identify it."""

    platform: SupportedPlatform
    # Patterns with a leading dot match the host or any subdomain.
    host_patterns: tuple[str, ...] = field(default_factory=tuple)


# Ordered most specific to least. ``local`` and ``generic`` are handled separately
# because they are not identified by vendor host patterns.
_ATS_RULES: tuple[_PlatformRule, ...] = (
    _PlatformRule(
        platform=SupportedPlatform(
            platform_id=PLATFORM_GREENHOUSE,
            display_name="Greenhouse",
            default_allowed_domains=[".greenhouse.io"],
            notes=(
                "Mostly standard HTML inputs. Company sites often embed the form in "
                "an iframe; the extension only sees the frame it runs in."
            ),
            supports_standard_inputs=True,
            supports_custom_selects=False,
            supports_iframes=True,
            risk_level=RISK_MEDIUM,
        ),
        host_patterns=(".greenhouse.io",),
    ),
    _PlatformRule(
        platform=SupportedPlatform(
            platform_id=PLATFORM_LEVER,
            display_name="Lever",
            default_allowed_domains=[".lever.co"],
            notes="Standard inputs with predictable name attributes.",
            supports_standard_inputs=True,
            supports_custom_selects=False,
            supports_iframes=False,
            risk_level=RISK_MEDIUM,
        ),
        host_patterns=(".lever.co",),
    ),
    _PlatformRule(
        platform=SupportedPlatform(
            platform_id=PLATFORM_ASHBY,
            display_name="Ashby",
            default_allowed_domains=[".ashbyhq.com"],
            notes="React-controlled inputs; native setters are required to fill them.",
            supports_standard_inputs=True,
            supports_custom_selects=False,
            supports_iframes=False,
            risk_level=RISK_MEDIUM,
        ),
        host_patterns=(".ashbyhq.com",),
    ),
    _PlatformRule(
        platform=SupportedPlatform(
            platform_id=PLATFORM_WORKDAY,
            display_name="Workday",
            default_allowed_domains=[".myworkdayjobs.com", ".myworkdaysite.com"],
            notes=(
                "Highly dynamic, heavy use of custom controls and multi-step wizards. "
                "Only plain text inputs are attempted; everything else is manual review."
            ),
            supports_standard_inputs=True,
            supports_custom_selects=False,
            supports_iframes=False,
            risk_level=RISK_HIGH,
        ),
        host_patterns=(".myworkdayjobs.com", ".myworkdaysite.com"),
    ),
    _PlatformRule(
        platform=SupportedPlatform(
            platform_id=PLATFORM_SMARTRECRUITERS,
            display_name="SmartRecruiters",
            default_allowed_domains=[".smartrecruiters.com"],
            notes=(
                "Dynamic form sections and custom pickers. Standard inputs only; "
                "custom controls are manual review."
            ),
            supports_standard_inputs=True,
            supports_custom_selects=False,
            supports_iframes=True,
            risk_level=RISK_HIGH,
        ),
        host_patterns=(".smartrecruiters.com",),
    ),
)

_LOCAL_PLATFORM = SupportedPlatform(
    platform_id=PLATFORM_LOCAL,
    display_name="Local sample form",
    default_allowed_domains=sorted(_LOCAL_ORIGINS),
    notes="Phase 6 behaviour, unchanged: loopback pages need no confirmation.",
    supports_standard_inputs=True,
    supports_custom_selects=False,
    supports_iframes=False,
    risk_level=RISK_LOW,
)

_GENERIC_PLATFORM = SupportedPlatform(
    platform_id=PLATFORM_GENERIC,
    display_name="Company-hosted application form",
    # Intentionally empty: opt in per host via PHASE7_APPROVED_DOMAINS.
    default_allowed_domains=[],
    notes=(
        "No domains are allowed by default. Add a specific host to the "
        f"{APPROVED_DOMAINS_ENV_VAR} environment variable and restart the backend."
    ),
    supports_standard_inputs=True,
    supports_custom_selects=False,
    supports_iframes=False,
    risk_level=RISK_HIGH,
)


def normalize_domain(url: str) -> str:
    """Return the lowercased host of ``url`` without a port, or "" if unparseable."""

    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ""
    host = (parts.hostname or "").strip().lower()
    # A trailing dot is a legal but confusing FQDN form; treat it as equivalent.
    return host.rstrip(".")


def _origin_of(url: str) -> str:
    """Return ``scheme://host:port`` lowercased, or "" if unparseable."""

    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ""
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


def is_local_development_url(url: str) -> bool:
    """True for the Phase 6 loopback origins. Compared whole, never by substring."""

    return _origin_of(url) in _LOCAL_ORIGINS


def _host_matches(host: str, pattern: str) -> bool:
    """Match a host against one pattern on label boundaries only."""

    if not host or not pattern:
        return False
    pattern = pattern.lower()
    if pattern.startswith("."):
        bare = pattern[1:]
        return host == bare or host.endswith(pattern)
    return host == pattern


def get_approved_extra_domains() -> list[str]:
    """Hosts a developer opted in via ``PHASE7_APPROVED_DOMAINS``.

    Comma or whitespace separated. Entries are normalized to bare lowercase hosts,
    so both ``example.com`` and ``https://example.com/apply`` are accepted.
    """

    raw = os.environ.get(APPROVED_DOMAINS_ENV_VAR, "")
    entries: list[str] = []
    for chunk in raw.replace(",", " ").split():
        candidate = chunk.strip().lower().lstrip(".")
        if not candidate:
            continue
        # Accept a full URL as well as a bare host.
        host = normalize_domain(candidate) if "//" in candidate else candidate.split("/")[0]
        host = host.split(":")[0].rstrip(".")
        if host and host not in entries:
            entries.append(host)
    return entries


def get_supported_platforms() -> list[SupportedPlatform]:
    """Every platform Phase 7 knows about, most trusted first.

    The ``generic`` entry reflects the current ``PHASE7_APPROVED_DOMAINS`` value, so
    the popup can show the user exactly which company domains are enabled.
    """

    generic = _GENERIC_PLATFORM.model_copy(
        update={"default_allowed_domains": get_approved_extra_domains()}
    )
    return [_LOCAL_PLATFORM, *(rule.platform for rule in _ATS_RULES), generic]


def _find_ats_rule(host: str) -> Optional[_PlatformRule]:
    for rule in _ATS_RULES:
        if any(_host_matches(host, pattern) for pattern in rule.host_patterns):
            return rule
    return None


def detect_platform_from_url(page_url: str) -> PlatformDetection:
    """Identify the platform for a URL from the URL alone.

    Confidence reflects how certain the *URL* makes us, not how well the platform
    is supported: a vendor host is unambiguous (0.95), an opted-in company domain
    is a deliberate human choice (0.6), and anything else is 0.0.
    """

    origin = _origin_of(page_url)
    if not origin:
        return PlatformDetection(
            platform_id=PLATFORM_UNSUPPORTED,
            display_name="Unsupported page",
            confidence=0.0,
            matched_by=[],
            page_url=page_url,
            allowed=False,
            reason="The page URL could not be parsed.",
        )

    if is_local_development_url(page_url):
        return PlatformDetection(
            platform_id=PLATFORM_LOCAL,
            display_name=_LOCAL_PLATFORM.display_name,
            confidence=1.0,
            matched_by=[f"url:local-origin:{origin}"],
            page_url=page_url,
            allowed=True,
            reason="Loopback development page (Phase 6 behaviour).",
        )

    host = normalize_domain(page_url)
    scheme = urlsplit(page_url.strip()).scheme.lower()

    rule = _find_ats_rule(host)
    if rule is not None:
        matched = next(p for p in rule.host_patterns if _host_matches(host, p))
        warnings: list[str] = []
        if not rule.platform.enabled:
            warnings.append(f"{rule.platform.display_name} support is currently disabled.")
        if rule.platform.risk_level == RISK_HIGH:
            warnings.append(
                f"{rule.platform.display_name} pages are highly dynamic; expect many "
                "fields to be left for manual review."
            )
        return PlatformDetection(
            platform_id=rule.platform.platform_id,
            display_name=rule.platform.display_name,
            confidence=0.95,
            matched_by=[f"url:host-suffix:{matched}"],
            page_url=page_url,
            allowed=rule.platform.enabled and scheme == "https",
            reason=(
                f"Host matches the {rule.platform.display_name} pattern {matched}."
                if scheme == "https"
                else "Real platform pages must be served over https."
            ),
            warnings=warnings,
        )

    if host in get_approved_extra_domains():
        return PlatformDetection(
            platform_id=PLATFORM_GENERIC,
            display_name=_GENERIC_PLATFORM.display_name,
            confidence=0.6,
            matched_by=[f"url:approved-domain:{host}"],
            page_url=page_url,
            allowed=scheme == "https",
            reason=(
                f"'{host}' was approved locally via {APPROVED_DOMAINS_ENV_VAR}."
                if scheme == "https"
                else "Real platform pages must be served over https."
            ),
            warnings=[
                "Company-hosted forms vary widely; review every field before submitting."
            ],
        )

    return PlatformDetection(
        platform_id=PLATFORM_UNSUPPORTED,
        display_name="Unsupported page",
        confidence=0.0,
        matched_by=[],
        page_url=page_url,
        allowed=False,
        reason=(
            f"'{host or page_url}' is not a supported platform and was not approved "
            f"via {APPROVED_DOMAINS_ENV_VAR}."
        ),
    )


def is_url_allowed_for_phase7(page_url: str) -> PageSafetyDecision:
    """The authoritative decision about whether Phase 7 will analyze a page.

    Loopback pages are allowed without confirmation, preserving Phase 6 exactly.
    Every real page is allowed only with explicit user confirmation. Everything else
    is blocked.
    """

    detection = detect_platform_from_url(page_url)

    if detection.platform_id == PLATFORM_LOCAL:
        return PageSafetyDecision(
            allowed=True,
            platform_id=PLATFORM_LOCAL,
            reason="Local development page; no confirmation required.",
            requires_user_confirmation=False,
        )

    if not detection.allowed:
        return PageSafetyDecision(
            allowed=False,
            platform_id=detection.platform_id,
            reason=detection.reason,
            warnings=detection.warnings,
            requires_user_confirmation=False,
            blocked_reason=detection.reason,
        )

    warnings = list(detection.warnings)
    warnings.append(
        "Real application page: only safe fields are filled, nothing is submitted, "
        "and sensitive or legal questions are left for you."
    )
    return PageSafetyDecision(
        allowed=True,
        platform_id=detection.platform_id,
        reason=detection.reason,
        warnings=warnings,
        requires_user_confirmation=True,
    )
