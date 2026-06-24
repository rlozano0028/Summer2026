"""Browser-automation API routes (Phase 4).

These endpoints only operate on the approved local sample forms. No endpoint
accepts an arbitrary or external URL, and nothing is ever submitted.

The routes are defined as synchronous ``def`` functions on purpose: they call
Playwright's sync API, which cannot run inside the asyncio event loop. Starlette
runs sync routes in a worker thread, which keeps the sync code path simple and
shared with the CLI and tests.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.automation import AutofillResult, AutomationRequest, FillPlan
from app.models.candidate_profile import CandidateProfile
from app.services import profile_storage, sample_forms
from app.services.playwright_autofill import (
    PlaywrightSetupError,
    analyze_local_form,
    run_local_autofill,
)

router = APIRouter(prefix="/automation", tags=["automation"])


class SampleFormsResponse(BaseModel):
    """Response for GET /automation/sample-forms."""

    forms: list[str]


class AnalyzeRequest(BaseModel):
    """Body for /automation/analyze and /automation/dry-run."""

    form_name: str


class RunSampleRequest(BaseModel):
    """Body for /automation/run-sample (approved local forms only)."""

    form_name: str
    headless: bool = True
    dry_run: bool = False
    keep_browser_open: bool = False


def _load_profile_or_404() -> CandidateProfile:
    try:
        profile = profile_storage.load_profile()
    except profile_storage.ProfileStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No saved profile found. Upload and review/save a profile first "
                "before running automation."
            ),
        )
    return profile


def _resolve_form_or_400(form_name: str):
    try:
        return sample_forms.resolve_sample_form(form_name)
    except sample_forms.UnknownSampleFormError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sample-forms", response_model=SampleFormsResponse)
def get_sample_forms() -> SampleFormsResponse:
    """Return the known local sample form names."""

    return SampleFormsResponse(forms=sample_forms.list_sample_forms())


@router.post("/analyze", response_model=FillPlan)
def analyze(body: AnalyzeRequest) -> FillPlan:
    """Open a local sample form headlessly and return a fill plan (no filling)."""

    profile = _load_profile_or_404()
    form_path = _resolve_form_or_400(body.form_name)
    try:
        return analyze_local_form(form_path, profile, form_name=body.form_name)
    except PlaywrightSetupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/dry-run", response_model=AutofillResult)
def dry_run(body: AnalyzeRequest) -> AutofillResult:
    """Run autofill in dry-run mode: detect and plan, but type nothing."""

    profile = _load_profile_or_404()
    form_path = _resolve_form_or_400(body.form_name)
    request = AutomationRequest(
        form_name=body.form_name,
        headless=True,
        dry_run=True,
        keep_browser_open=False,
    )
    try:
        return run_local_autofill(form_path, profile, request)
    except PlaywrightSetupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/run-sample", response_model=AutofillResult)
def run_sample(body: RunSampleRequest) -> AutofillResult:
    """Run autofill against an approved local sample form. Never submits.

    For headful browser demos prefer the CLI; the API keeps browsers short-lived
    and never honors ``keep_browser_open`` server-side.
    """

    profile = _load_profile_or_404()
    form_path = _resolve_form_or_400(body.form_name)
    request = AutomationRequest(
        form_name=body.form_name,
        headless=body.headless,
        dry_run=body.dry_run,
        # The API never blocks on an open browser, regardless of the request.
        keep_browser_open=False,
    )
    try:
        return run_local_autofill(form_path, profile, request)
    except PlaywrightSetupError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
