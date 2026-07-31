"""Tests for the Phase 7 URL allow-list.

Everything here operates on URL strings. Nothing in these tests (or in the module
under test) performs DNS resolution, HTTP requests, or disk I/O, which is asserted
explicitly at the bottom of the file.
"""

from __future__ import annotations

import socket

import pytest

from app.models.platform import (
    PLATFORM_ASHBY,
    PLATFORM_GENERIC,
    PLATFORM_GREENHOUSE,
    PLATFORM_LEVER,
    PLATFORM_LOCAL,
    PLATFORM_SMARTRECRUITERS,
    PLATFORM_UNSUPPORTED,
    PLATFORM_WORKDAY,
)
from app.services import platform_allowlist
from app.services.platform_allowlist import (
    APPROVED_DOMAINS_ENV_VAR,
    detect_platform_from_url,
    get_approved_extra_domains,
    get_supported_platforms,
    is_local_development_url,
    is_url_allowed_for_phase7,
    normalize_domain,
)


# --- normalize_domain / is_local_development_url ------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://boards.greenhouse.io/acme/jobs/1", "boards.greenhouse.io"),
        ("https://BOARDS.Greenhouse.IO/acme", "boards.greenhouse.io"),
        ("https://boards.greenhouse.io.:443/acme", "boards.greenhouse.io"),
        ("http://127.0.0.1:8000/x", "127.0.0.1"),
        ("not a url", ""),
        ("", ""),
    ],
)
def test_normalize_domain_lowercases_and_strips_port(url: str, expected: str) -> None:
    assert normalize_domain(url) == expected


def test_local_origins_match_whole_origin_only() -> None:
    assert is_local_development_url("http://127.0.0.1:8000/sample-forms/basic.html")
    assert is_local_development_url("http://localhost:5173/")
    # Right host, wrong port; and a lookalike host that merely contains "127.0.0.1".
    assert not is_local_development_url("http://127.0.0.1:9999/")
    assert not is_local_development_url("http://127.0.0.1.evil.example.com:8000/")


# --- vendor detection ---------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "platform_id"),
    [
        ("https://boards.greenhouse.io/acme/jobs/1", PLATFORM_GREENHOUSE),
        ("https://greenhouse.io/acme", PLATFORM_GREENHOUSE),
        ("https://jobs.lever.co/acme/1234", PLATFORM_LEVER),
        ("https://jobs.ashbyhq.com/acme/1234", PLATFORM_ASHBY),
        ("https://acme.wd5.myworkdayjobs.com/en-US/careers/job/1", PLATFORM_WORKDAY),
        ("https://acme.wd1.myworkdaysite.com/recruiting/job", PLATFORM_WORKDAY),
        ("https://jobs.smartrecruiters.com/Acme/12345", PLATFORM_SMARTRECRUITERS),
    ],
)
def test_supported_vendors_are_detected_and_allowed(url: str, platform_id: str) -> None:
    detection = detect_platform_from_url(url)
    assert detection.platform_id == platform_id
    assert detection.allowed is True
    assert detection.confidence >= 0.9
    assert detection.matched_by

    safety = is_url_allowed_for_phase7(url)
    assert safety.allowed is True
    assert safety.requires_user_confirmation is True


@pytest.mark.parametrize(
    "url",
    [
        # Suffix appears in the middle: matching must be on label boundaries.
        "https://boards.greenhouse.io.evil.example.com/acme",
        # Suffix appears at the start of a longer label.
        "https://notgreenhouse.io/acme",
        "https://lever.co.attacker.test/acme",
        "https://myworkdayjobs.com.evil.test/job",
    ],
)
def test_lookalike_hosts_are_blocked(url: str) -> None:
    detection = detect_platform_from_url(url)
    assert detection.platform_id == PLATFORM_UNSUPPORTED
    assert detection.allowed is False

    safety = is_url_allowed_for_phase7(url)
    assert safety.allowed is False
    assert safety.blocked_reason


def test_real_platforms_require_https() -> None:
    safety = is_url_allowed_for_phase7("http://boards.greenhouse.io/acme/jobs/1")
    assert safety.allowed is False
    assert "https" in (safety.blocked_reason or "").lower()


def test_unparseable_url_fails_closed() -> None:
    for url in ["", "   ", "javascript:alert(1)", "boards.greenhouse.io/acme"]:
        safety = is_url_allowed_for_phase7(url)
        assert safety.allowed is False, url
        assert safety.blocked_reason, url


# --- local pages --------------------------------------------------------------


def test_local_page_is_allowed_without_confirmation() -> None:
    safety = is_url_allowed_for_phase7("http://127.0.0.1:8000/sample-forms/basic.html")
    assert safety.allowed is True
    assert safety.platform_id == PLATFORM_LOCAL
    assert safety.requires_user_confirmation is False


def test_local_fixture_page_is_local_by_url() -> None:
    """A greenhouse-shaped fixture on loopback is still just a local page."""

    detection = detect_platform_from_url(
        "http://127.0.0.1:8000/test-fixtures/platform-pages/greenhouse-like.html"
    )
    assert detection.platform_id == PLATFORM_LOCAL


# --- generic / approved domains ----------------------------------------------


def test_generic_domain_is_blocked_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(APPROVED_DOMAINS_ENV_VAR, raising=False)
    safety = is_url_allowed_for_phase7("https://careers.acme-corp.example/apply")
    assert safety.allowed is False
    assert APPROVED_DOMAINS_ENV_VAR in (safety.blocked_reason or "")


def test_approved_domain_is_allowed_with_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(APPROVED_DOMAINS_ENV_VAR, "careers.acme-corp.example")
    detection = detect_platform_from_url("https://careers.acme-corp.example/apply")
    assert detection.platform_id == PLATFORM_GENERIC
    assert detection.allowed is True

    safety = is_url_allowed_for_phase7("https://careers.acme-corp.example/apply")
    assert safety.allowed is True
    assert safety.requires_user_confirmation is True


def test_approved_domains_do_not_cover_subdomains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Approval is per host, so a subdomain must be listed separately."""

    monkeypatch.setenv(APPROVED_DOMAINS_ENV_VAR, "acme-corp.example")
    assert is_url_allowed_for_phase7("https://acme-corp.example/apply").allowed is True
    assert (
        is_url_allowed_for_phase7("https://careers.acme-corp.example/apply").allowed
        is False
    )


@pytest.mark.parametrize(
    "raw",
    [
        "one.example, two.example",
        "one.example two.example",
        " ONE.example ,, two.example ",
        "https://one.example/apply two.example",
        ".one.example,two.example:443",
    ],
)
def test_env_var_parsing_accepts_commas_whitespace_and_urls(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv(APPROVED_DOMAINS_ENV_VAR, raw)
    assert get_approved_extra_domains() == ["one.example", "two.example"]


def test_empty_env_var_yields_no_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(APPROVED_DOMAINS_ENV_VAR, "   ")
    assert get_approved_extra_domains() == []


# --- platform registry --------------------------------------------------------


def test_supported_platforms_lists_every_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(APPROVED_DOMAINS_ENV_VAR, "careers.acme-corp.example")
    platforms = get_supported_platforms()
    ids = [platform.platform_id for platform in platforms]
    assert ids == [
        PLATFORM_LOCAL,
        PLATFORM_GREENHOUSE,
        PLATFORM_LEVER,
        PLATFORM_ASHBY,
        PLATFORM_WORKDAY,
        PLATFORM_SMARTRECRUITERS,
        PLATFORM_GENERIC,
    ]
    generic = platforms[-1]
    assert generic.default_allowed_domains == ["careers.acme-corp.example"]
    # No platform claims it can drive custom controls.
    assert all(not platform.supports_custom_selects for platform in platforms)


def test_detection_never_touches_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any socket use would mean we are contacting a real site. Fail loudly."""

    def explode(*args: object, **kwargs: object) -> None:
        raise AssertionError("platform_allowlist must not use the network")

    monkeypatch.setattr(socket, "getaddrinfo", explode)
    monkeypatch.setattr(socket, "create_connection", explode)
    monkeypatch.setattr(socket.socket, "connect", explode)

    for url in [
        "https://boards.greenhouse.io/acme/jobs/1",
        "https://evil.example/apply",
        "http://127.0.0.1:8000/x",
    ]:
        detect_platform_from_url(url)
        is_url_allowed_for_phase7(url)


def test_module_exposes_no_fetching_helpers() -> None:
    """A guard against someone later adding a "just fetch the page" helper."""

    suspicious = [
        name
        for name in dir(platform_allowlist)
        if any(word in name.lower() for word in ("fetch", "request", "download", "open_url"))
    ]
    assert suspicious == []
