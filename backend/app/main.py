"""FastAPI application entry point.

Run locally with:
    uvicorn app.main:app --reload
(from the ``backend`` directory, with the virtual environment activated).
"""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.api.routes import resume

app = FastAPI(
    title="Resume Autofill Assistant",
    description=(
        "Local-first personal job-application autofill assistant. "
        "Phase 1-2: candidate profile schema and resume ingestion/parsing."
    ),
    version=__version__,
)

# All routes live under the resume router (includes /health).
app.include_router(resume.router)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    """Friendly root pointing at the docs."""

    return {
        "name": "Resume Autofill Assistant",
        "version": __version__,
        "docs": "/docs",
    }
