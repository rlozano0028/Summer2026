"""FastAPI application entry point.

Run locally with:
    uvicorn app.main:app --reload
(from the ``backend`` directory, with the virtual environment activated).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import (
    automation,
    extension,
    mapping_overrides,
    platform_support,
    profile,
    resume,
)
from app.services.sample_forms import get_sample_forms_dir

# backend/app/main.py -> repository root is parents[2].
TEST_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "test-fixtures"

app = FastAPI(
    title="Resume Autofill Assistant",
    description=(
        "Local-first personal job-application autofill assistant. "
        "Phase 1-7: profile schema, resume ingestion/parsing, local dashboard "
        "profile storage, a local-only browser-automation prototype, an "
        "explainable field-mapping engine with local mapping overrides, a "
        "local Chrome extension integration, and controlled, user-activated "
        "support for real application platforms."
    ),
    version=__version__,
)

# Local development only: allow the Vite dev server origins so the React
# dashboard can call this API from the browser. These are loopback origins on a
# developer machine; do NOT broaden this for a real deployment.
#
# Phase 6 adds the loopback origins used to host sample forms, plus a regex for
# the Chrome extension popup. A packed extension's origin is
# ``chrome-extension://<32-char id>`` and that id is not known until the unpacked
# extension is loaded, so the id itself cannot be pinned here. The regex is
# deliberately narrow (extension origins only, no wildcard hosts) and is still a
# development-only allowance.
LOCAL_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
LOCAL_EXTENSION_ORIGIN_REGEX = r"^chrome-extension://[a-z]{32}$"
app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_DEV_ORIGINS,
    allow_origin_regex=LOCAL_EXTENSION_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# resume.router includes /health, /resume/*; profile.router adds /profile/*.
app.include_router(resume.router)
app.include_router(profile.router)
app.include_router(automation.router)
app.include_router(mapping_overrides.router)
app.include_router(extension.router)
app.include_router(platform_support.router)

# Phase 6: serve the repo's sample forms over http so the Chrome extension can be
# tested on real pages (extensions are awkward to use on file:// URLs). This is a
# read-only mount of files already in the repo; the Playwright prototype keeps
# loading them from disk and is unaffected. ``check_dir=False`` keeps app import
# working when the directory is absent or overridden via SAMPLE_FORMS_DIR.
app.mount(
    "/sample-forms",
    StaticFiles(directory=str(get_sample_forms_dir()), check_dir=False, html=False),
    name="sample-forms",
)

# Phase 7: serve the synthetic platform fixture pages the same read-only way. These
# imitate the DOM shape of real ATS forms so the platform adapters can be exercised
# on loopback, where no confirmation is required and nothing can be submitted. No
# real job site is ever fetched or mirrored.
app.mount(
    "/test-fixtures",
    StaticFiles(directory=str(TEST_FIXTURES_DIR), check_dir=False, html=False),
    name="test-fixtures",
)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    """Friendly root pointing at the docs."""

    return {
        "name": "Resume Autofill Assistant",
        "version": __version__,
        "docs": "/docs",
    }
