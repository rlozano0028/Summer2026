"""Chrome-extension API routes (Phase 6).

These endpoints exist so a local Chrome extension can get a Phase 5 fill plan for
the page it is currently on. They analyze *field metadata only*:

- No browser is opened or driven here (that stays in the Phase 4 Playwright
  prototype, which is untouched).
- ``page_url`` is never fetched. It is used for the local allow-list check and to
  label the plan.
- Nothing from the page is persisted, and resolved fill values are returned in a
  transient response body only - never written to a report or log.

``POST /extension/analyze-page`` is restricted to loopback development origins
(:data:`app.models.extension.ALLOWED_PAGE_ORIGINS`) and behaves exactly as it did
in Phase 6: an external URL is rejected outright rather than warned about.

Phase 7 adds a *separate* endpoint, ``POST /extension/analyze-real-page``, for
pages the user opened themselves on an explicitly supported platform. It applies
the same metadata-only, never-submit rules plus an allow-list check, a required
user confirmation, and a final value-stripping pass. The Phase 6 endpoint is
deliberately left untouched so its behaviour cannot regress.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException

from app import __version__
from app.models.extension import (
    ALLOWED_PAGE_ORIGINS,
    ExtensionAnalyzeRequest,
    ExtensionAnalyzeResponse,
    ExtensionHealthResponse,
    ExtensionValidatePageRequest,
    ExtensionValidatePageResponse,
)
from app.models.candidate_profile import CandidateProfile
from app.models.platform import (
    RealPlatformAnalyzeRequest,
    RealPlatformAnalyzeResponse,
)
from app.services import profile_storage, sample_forms
from app.services.extension_field_adapter import (
    build_extension_response,
    build_fill_instructions,
    convert_extension_fields_to_form_fields,
)
from app.services.field_mapper import build_fill_plan
from app.services.platform_allowlist import detect_platform_from_url
from app.services.platform_policy import (
    build_real_platform_warnings,
    downgrade_unsupported_fields,
    enforce_instruction_safety,
    validate_real_platform_request,
)

router = APIRouter(prefix="/extension", tags=["extension"])

# Label used for override lookups when the extension does not supply a form name.
DEFAULT_FORM_NAME = "extension-page"


def is_allowed_page_url(page_url: str) -> bool:
    """Return True if ``page_url`` is on a Phase 6 loopback development origin.

    Compares scheme+host+port exactly, so a lookalike host such as
    ``http://127.0.0.1.evil.com:8000`` does not pass.
    """

    try:
        parts = urlsplit(page_url.strip())
    except ValueError:
        return False
    if not parts.scheme or not parts.netloc:
        return False
    origin = f"{parts.scheme.lower()}://{parts.netloc.lower()}"
    return origin in ALLOWED_PAGE_ORIGINS


def resolve_form_name(requested: Optional[str], page_url: str) -> str:
    """Pick the label used to look up Phase 5 mapping overrides.

    When the page is one of the repo's sample forms, this normalizes to that
    form's short name (``basic-application.html`` -> ``basic``) so an override
    saved from the dashboard also applies when the extension analyzes the same
    form. Anything else falls back to the caller's label, then to
    :data:`DEFAULT_FORM_NAME`.
    """

    candidates = [
        (requested or "").strip(),
        urlsplit(page_url).path.rsplit("/", 1)[-1].strip(),
    ]
    filename_to_short = {
        filename.lower(): short for short, filename in sample_forms.KNOWN_FORMS.items()
    }
    for candidate in candidates:
        if not candidate:
            continue
        key = candidate.lower()
        if key in sample_forms.KNOWN_FORMS:
            return key
        if key in filename_to_short:
            return filename_to_short[key]
    return next((c for c in candidates if c), DEFAULT_FORM_NAME)


def _allowlist_reason(page_url: str) -> str:
    allowed = ", ".join(ALLOWED_PAGE_ORIGINS)
    return (
        f"Page '{page_url}' is not a supported Phase 6 page. The Chrome extension "
        f"only works on local development pages: {allowed}."
    )


def _load_profile_or_error() -> CandidateProfile:
    """Load the saved profile, raising the HTTP errors the popup expects."""

    try:
        profile = profile_storage.load_profile()
    except profile_storage.ProfileStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No saved profile found. Upload a resume and save a reviewed "
                "profile in the local dashboard before using the extension."
            ),
        )
    return profile


@router.get("/health", response_model=ExtensionHealthResponse)
def extension_health() -> ExtensionHealthResponse:
    """Report backend reachability and saved-profile status for the popup."""

    exists = profile_storage.profile_exists()
    if not exists:
        return ExtensionHealthResponse(
            ok=True,
            backend=f"Resume Autofill Assistant {__version__}",
            profile_exists=False,
            profile_needs_review=None,
            message=(
                "Backend is reachable, but no saved profile was found. Upload and "
                "review a resume in the local dashboard first."
            ),
        )

    try:
        profile = profile_storage.load_profile()
    except profile_storage.ProfileStorageError as exc:
        return ExtensionHealthResponse(
            ok=False,
            backend=f"Resume Autofill Assistant {__version__}",
            profile_exists=True,
            profile_needs_review=None,
            message=f"A saved profile exists but could not be read: {exc}",
        )

    needs_review = profile.metadata.needs_review if profile else None
    message = (
        "Backend reachable. Saved profile still needs review - check it in the "
        "dashboard before trusting autofill."
        if needs_review
        else "Backend reachable and a reviewed profile is available."
    )
    return ExtensionHealthResponse(
        ok=True,
        backend=f"Resume Autofill Assistant {__version__}",
        profile_exists=True,
        profile_needs_review=needs_review,
        message=message,
    )


@router.post("/validate-page", response_model=ExtensionValidatePageResponse)
def validate_page(body: ExtensionValidatePageRequest) -> ExtensionValidatePageResponse:
    """Tell the popup whether a page is in scope for Phase 6."""

    allowed = is_allowed_page_url(body.page_url)
    return ExtensionValidatePageResponse(
        page_url=body.page_url,
        allowed=allowed,
        reason=(
            "Local development page supported in Phase 6."
            if allowed
            else _allowlist_reason(body.page_url)
        ),
        allowed_origins=list(ALLOWED_PAGE_ORIGINS),
    )


@router.post("/analyze-page", response_model=ExtensionAnalyzeResponse)
def analyze_page(body: ExtensionAnalyzeRequest) -> ExtensionAnalyzeResponse:
    """Build a Phase 5 fill plan from extension-detected field metadata."""

    if not is_allowed_page_url(body.page_url):
        raise HTTPException(status_code=400, detail=_allowlist_reason(body.page_url))

    try:
        profile = profile_storage.load_profile()
    except profile_storage.ProfileStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No saved profile found. Upload a resume and save a reviewed "
                "profile in the local dashboard before using the extension."
            ),
        )

    if not body.fields:
        raise HTTPException(
            status_code=400,
            detail="No fields were sent. Run 'Detect fields' on the page first.",
        )

    warnings: list[str] = []
    if profile.metadata.needs_review:
        warnings.append(
            "Saved profile is still marked as needing review; verify every value "
            "before submitting the form."
        )

    form_fields, dropped_password_ids = convert_extension_fields_to_form_fields(body.fields)
    if dropped_password_ids:
        warnings.append(
            f"Ignored {len(dropped_password_ids)} password field(s); the extension "
            "never reads or fills passwords."
        )
    if not form_fields:
        raise HTTPException(
            status_code=400,
            detail="No analyzable fields remained after removing password inputs.",
        )

    form_name = resolve_form_name(body.form_name, body.page_url)
    fill_plan = build_fill_plan(form_name, body.page_url, form_fields, profile)

    return build_extension_response(
        page_url=body.page_url,
        page_title=body.page_title,
        fill_plan=fill_plan,
        profile=profile,
        fields=body.fields,
        warnings=warnings,
    )


@router.post("/analyze-real-page", response_model=RealPlatformAnalyzeResponse)
def analyze_real_page(body: RealPlatformAnalyzeRequest) -> RealPlatformAnalyzeResponse:
    """Build a fill plan for a real application page the user opened (Phase 7).

    Order of operations matters here, and each step can only narrow what happens:

    1. The URL is checked against the platform allow-list, and a real page is
       refused without ``user_confirmed_real_page``.
    2. Password inputs are dropped, exactly as in Phase 6.
    3. The unchanged Phase 5 engine produces the plan.
    4. Custom controls are downgraded to manual review.
    5. :func:`enforce_instruction_safety` strips any value that is not provably safe.

    ``body.platform_id`` and ``body.platform_confidence`` are hints from the
    extension's DOM signals. They are reported back for display but never widen
    access: the platform used for the safety decision is re-derived from the URL.

    Like every endpoint here, this opens no browser, fetches no URL, writes no file,
    and never returns anything that would let the caller submit the form.
    """

    safety = validate_real_platform_request(body.page_url, body.user_confirmed_real_page)
    if not safety.allowed:
        raise HTTPException(
            status_code=400, detail=safety.blocked_reason or safety.reason
        )

    detection = detect_platform_from_url(body.page_url)
    # The extension's DOM-signal opinion is advisory; record it when it disagrees
    # so a confusing plan can be explained later.
    if body.platform_id and body.platform_id != detection.platform_id:
        detection = detection.model_copy(
            update={
                "matched_by": [
                    *detection.matched_by,
                    f"page-signal:{body.platform_id}",
                ]
            }
        )
    detection = detection.model_copy(update={"allowed": safety.allowed})

    profile = _load_profile_or_error()

    warnings: list[str] = []
    if profile.metadata.needs_review:
        warnings.append(
            "Saved profile is still marked as needing review; verify every value "
            "before submitting the form."
        )

    form_fields, dropped_password_ids = convert_extension_fields_to_form_fields(body.fields)
    if dropped_password_ids:
        warnings.append(
            f"Ignored {len(dropped_password_ids)} password field(s); the extension "
            "never reads or fills passwords."
        )

    # Overrides for real pages are keyed by platform, not by page: two job postings
    # on the same ATS share the same field shapes, and the URL usually carries a
    # per-posting id that would make a per-URL key useless.
    form_name = detection.platform_id
    fill_plan = build_fill_plan(form_name, body.page_url, form_fields, profile)
    fill_plan, unsupported_count = downgrade_unsupported_fields(fill_plan, body.fields)

    instructions, resolve_warnings = build_fill_instructions(fill_plan, profile, body.fields)
    instructions, withheld_warnings = enforce_instruction_safety(instructions, body.fields)

    warnings.extend(resolve_warnings)
    warnings.extend(withheld_warnings)
    warnings.extend(
        build_real_platform_warnings(safety, body.fields, unsupported_count)
    )

    deduped: list[str] = []
    for warning in warnings:
        if warning not in deduped:
            deduped.append(warning)

    return RealPlatformAnalyzeResponse(
        page_url=body.page_url,
        page_title=body.page_title,
        platform=detection,
        safety=safety,
        warnings=deduped,
        fill_plan=fill_plan,
        instructions=instructions,
        unsupported_count=unsupported_count,
    )
