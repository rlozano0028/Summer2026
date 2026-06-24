"""FastAPI application entry point.

Run locally with:
    uvicorn app.main:app --reload
(from the ``backend`` directory, with the virtual environment activated).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import automation, mapping_overrides, profile, resume

app = FastAPI(
    title="Resume Autofill Assistant",
    description=(
        "Local-first personal job-application autofill assistant. "
        "Phase 1-5: profile schema, resume ingestion/parsing, local dashboard "
        "profile storage, a local-only browser-automation prototype, and an "
        "explainable field-mapping engine with local mapping overrides."
    ),
    version=__version__,
)

# Local development only: allow the Vite dev server origins so the React
# dashboard can call this API from the browser. These are loopback origins on a
# developer machine; do NOT broaden this for a real deployment.
LOCAL_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_DEV_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# resume.router includes /health, /resume/*; profile.router adds /profile/*.
app.include_router(resume.router)
app.include_router(profile.router)
app.include_router(automation.router)
app.include_router(mapping_overrides.router)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    """Friendly root pointing at the docs."""

    return {
        "name": "Resume Autofill Assistant",
        "version": __version__,
        "docs": "/docs",
    }
