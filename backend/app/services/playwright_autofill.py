"""Playwright-driven autofill for local sample forms (Phase 4).

This module is intentionally isolated from resume parsing and from any future
Chrome-extension work. It only ever opens local HTML files (``file://`` URLs);
it never navigates to real job sites and never clicks submit controls.

Concurrency note: this uses Playwright's *sync* API. FastAPI routes that call
into it are defined as plain ``def`` functions so Starlette runs them in a
worker thread, avoiding the "sync API inside asyncio loop" error.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from app.models.automation import (
    ACTION_FILL,
    ACTION_MANUAL_REVIEW,
    ACTION_SKIP,
    ACTION_SUGGEST,
    AutofillResult,
    AutomationRequest,
    FieldMapping,
    FillPlan,
    FormField,
)
from app.models.candidate_profile import CandidateProfile
from app.services import automation_report_storage
from app.services.field_mapper import build_fill_plan, resolve_fill_value
from app.services.form_field_detector import detect_form_fields

if TYPE_CHECKING:
    from playwright.sync_api import Page

# Install hint surfaced whenever the browser cannot be launched.
INSTALL_HINT = (
    "Playwright could not launch Chromium. Install the browser binaries with:\n"
    "    python -m playwright install chromium"
)


class PlaywrightSetupError(RuntimeError):
    """Raised when Playwright or its browser binaries are unavailable."""


def _path_to_file_url(form_path: Path) -> str:
    """Convert a local path to a cross-platform ``file://`` URL."""

    return form_path.resolve().as_uri()


def _label_for(field: FormField) -> str:
    return field.label_text or field.name or field.id_attribute or field.field_id


def analyze_local_form(
    form_path: Path,
    profile: CandidateProfile,
    form_name: str | None = None,
) -> FillPlan:
    """Open a local form headlessly, detect fields, and build a fill plan.

    Nothing is filled and the browser is always closed before returning.
    ``form_name`` should be the short sample-form name (e.g. ``"basic"``) so it
    matches the key used when saving mapping overrides; it defaults to the file
    stem when omitted.
    """

    resolved_name = form_name or form_path.stem
    form_url = _path_to_file_url(form_path)

    with _launch_browser(headless=True) as (browser, page):
        page.goto(form_url)
        fields = detect_form_fields(page)
        browser.close()

    return build_fill_plan(resolved_name, form_url, fields, profile)


def run_local_autofill(
    form_path: Path,
    profile: CandidateProfile,
    request: AutomationRequest,
) -> AutofillResult:
    """Detect, plan, and (unless dry-run) fill a local form. Never submits."""

    form_name = request.form_name or form_path.stem
    form_url = _path_to_file_url(form_path)
    started_at = datetime.now(timezone.utc)

    filled: list[str] = []
    suggested: list[str] = []
    manual_review: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []

    with _launch_browser(headless=request.headless) as (browser, page):
        page.goto(form_url)
        fields = detect_form_fields(page)
        plan = build_fill_plan(form_name, form_url, fields, profile)
        warnings.extend(plan.warnings)
        field_by_id = {field.field_id: field for field in fields}

        for mapping in plan.mappings:
            field = field_by_id.get(mapping.field_id)
            label = _label_for(field) if field else mapping.field_id
            tooltip = _tooltip_for(mapping)

            if mapping.action == ACTION_SUGGEST:
                suggested.append(label)
                _mark_field(page, mapping.selector, "suggest", tooltip)
                continue
            if mapping.action == ACTION_MANUAL_REVIEW:
                manual_review.append(label)
                _mark_field(page, mapping.selector, "manual", tooltip)
                continue
            if mapping.action == ACTION_SKIP:
                skipped.append(label)
                _mark_field(page, mapping.selector, "skip", tooltip)
                continue
            if mapping.action != ACTION_FILL:
                skipped.append(label)
                continue

            if field is None:
                warnings.append(f"Could not locate field to fill: {label}")
                continue
            would_fill = _try_fill(
                page=page,
                field=field,
                mapping=mapping,
                profile=profile,
                request=request,
                dry_run=request.dry_run,
                warnings=warnings,
            )
            if request.dry_run:
                # Honest accounting: nothing was typed during a dry run.
                suggested.append(f"{label} (would fill)")
                _mark_field(page, mapping.selector, "suggest", tooltip)
            elif would_fill:
                filled.append(label)
                _mark_field(page, mapping.selector, "filled", tooltip)
            else:
                manual_review.append(label)
                _mark_field(page, mapping.selector, "manual", tooltip)

        if request.dry_run:
            warnings.append(
                f"Dry run: {plan.fill_count} field(s) would be filled; nothing was typed."
            )

        # Optional manual-debugging pause (CLI only; API always passes False).
        if request.keep_browser_open and not request.headless:
            print("\nBrowser left open for inspection. Press Enter to close...")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                pass

        browser.close()

    completed_at = datetime.now(timezone.utc)
    result = AutofillResult(
        form_name=form_name,
        form_url=form_url,
        started_at=started_at,
        completed_at=completed_at,
        filled_fields=filled,
        suggested_fields=suggested,
        manual_review_fields=manual_review,
        skipped_fields=skipped,
        warnings=warnings,
        success=True,
        plan=plan,
    )
    report_path = automation_report_storage.save_report(result)
    result.report_path = str(report_path)
    return result


def _try_fill(
    *,
    page: "Page",
    field: FormField,
    mapping: FieldMapping,
    profile: CandidateProfile,
    request: AutomationRequest,
    dry_run: bool,
    warnings: list[str],
) -> bool:
    """Attempt to fill a single field. Returns True if it was (or would be) filled.

    Conservative by design: checkboxes/radios are deferred, selects only fill on
    a confident option match, and file inputs only fill with an explicit resume
    path. On a dry run nothing is typed but eligibility is still reported.
    """

    label = _label_for(field)
    input_type = (field.input_type or "").lower()

    # Checkboxes / radios are intentionally deferred in Phase 4.
    if input_type in {"checkbox", "radio"}:
        warnings.append(f"Checkbox/radio deferred to manual review: {label}")
        return False

    # File inputs handled separately (resume only, with explicit path).
    if field.is_file_upload:
        return _try_set_resume(page, field, request, dry_run, warnings)

    value = resolve_fill_value(profile, mapping.profile_path)
    if value is None:
        warnings.append(f"No value resolved for field: {label}")
        return False

    if field.tag_name == "select":
        return _try_select(page, field, value, dry_run, warnings)

    if dry_run:
        return True
    try:
        page.locator(mapping.selector).fill(value)
        return True
    except Exception as exc:  # noqa: BLE001 - report, don't crash the run.
        warnings.append(f"Failed to fill '{label}': {type(exc).__name__}")
        return False


def _try_select(
    page: "Page",
    field: FormField,
    value: str,
    dry_run: bool,
    warnings: list[str],
) -> bool:
    """Select an option only when there is a confident normalized match."""

    target = value.strip().lower()
    match = next(
        (opt for opt in field.options if opt.strip().lower() == target),
        None,
    )
    if match is None:
        warnings.append(
            f"No confident option match for select '{_label_for(field)}' - left unchanged."
        )
        return False
    if dry_run:
        return True
    try:
        page.locator(field.selector).select_option(match)
        return True
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Failed to select option for '{_label_for(field)}': {type(exc).__name__}")
        return False


def _try_set_resume(
    page: "Page",
    field: FormField,
    request: AutomationRequest,
    dry_run: bool,
    warnings: list[str],
) -> bool:
    """Attach a resume file only when an explicit, existing local path is given."""

    if not request.resume_file_path:
        warnings.append(f"File upload left for manual review (no resume path): {_label_for(field)}")
        return False
    resume_path = Path(request.resume_file_path)
    if not resume_path.is_file():
        warnings.append(f"Resume file not found, left for manual review: {resume_path}")
        return False
    if dry_run:
        return True
    try:
        page.locator(field.selector).set_input_files(str(resume_path))
        return True
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Failed to attach resume: {type(exc).__name__}")
        return False


def _tooltip_for(mapping: FieldMapping) -> str:
    """Build a short, private-value-free tooltip for local debugging.

    Only the action, category, and confidence are exposed - never a value.
    """

    confidence = f"{mapping.confidence:.2f}" if mapping.confidence else "0.00"
    return f"[{mapping.action}] {mapping.category} (confidence {confidence})"


def _mark_field(page: "Page", selector: str, kind: str, title: str = "") -> None:
    """Best-effort visual marking for local debugging only.

    Outlines the field by action and sets a ``title`` tooltip. The tooltip never
    contains a private value (only action/category/confidence).
    """

    colors = {
        "filled": "#16a34a",  # green - will fill
        "suggest": "#d97706",  # amber - suggested
        "manual": "#dc2626",  # red - manual review
        "skip": "#9aa5b1",  # gray - skipped
    }
    color = colors.get(kind, "#2563eb")
    try:
        page.eval_on_selector(
            selector,
            """(el, args) => {
                el.style.outline = '2px solid ' + args.color;
                if (args.title) { el.title = args.title; }
            }""",
            {"color": color, "title": title},
        )
    except Exception:  # noqa: BLE001 - marking is cosmetic; never fail the run.
        pass


class _BrowserSession:
    """Context manager yielding ``(browser, page)`` with clear setup errors."""

    def __init__(self, headless: bool) -> None:
        self._headless = headless
        self._playwright = None
        self._browser = None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # Playwright not installed at all.
            raise PlaywrightSetupError(
                "Playwright is not installed. Install it with 'pip install playwright' "
                "and then run 'python -m playwright install chromium'."
            ) from exc

        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(headless=self._headless)
        except Exception as exc:  # noqa: BLE001 - usually missing browser binary.
            self._playwright.stop()
            raise PlaywrightSetupError(f"{INSTALL_HINT}\n\nOriginal error: {exc}") from exc
        page = self._browser.new_page()
        return self._browser, page

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:  # noqa: BLE001
            pass
        finally:
            if self._playwright is not None:
                self._playwright.stop()


def _launch_browser(headless: bool) -> _BrowserSession:
    return _BrowserSession(headless=headless)
