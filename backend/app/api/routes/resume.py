"""Resume upload API routes (Phase 2).

Uploaded files are written to a temporary location, processed, and then
deleted. Nothing is stored permanently in this phase.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.resume import ResumeParseResult
from app.services.resume_profile_parser import parse_resume_text_to_profile
from app.services.resume_text_extractor import extract_text_from_resume
from app.utils.file_validation import SUPPORTED_EXTENSIONS, ResumeValidationError

router = APIRouter()

# Number of characters returned as a preview from the extract-text endpoint.
PREVIEW_CHARS = 2000


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Simple liveness check."""

    return {"status": "ok"}


def _suffix_for(filename: Optional[str]) -> str:
    """Return the lower-cased suffix of an uploaded filename (with the dot)."""

    if not filename:
        return ""
    return Path(filename).suffix.lower()


def _save_upload_to_temp(upload: UploadFile) -> Path:
    """Persist an UploadFile to a NamedTemporaryFile and return its path."""

    suffix = _suffix_for(upload.filename)
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(upload.file.read())
        return Path(tmp.name)


def _reject_unsupported(upload: UploadFile) -> None:
    """Fast pre-check so we don't write temp files for unsupported types."""

    suffix = _suffix_for(upload.filename)
    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{suffix or '(none)'}'. "
                f"Supported types are: {supported}."
            ),
        )


@router.post("/resume/extract-text", tags=["resume"])
async def extract_text_endpoint(file: UploadFile = File(...)) -> dict[str, object]:
    """Extract text from an uploaded resume and return metadata + a preview."""

    _reject_unsupported(file)
    temp_path = _save_upload_to_temp(file)
    try:
        extracted = extract_text_from_resume(temp_path)
    except ResumeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    text = extracted.text
    return {
        "file_name": file.filename,
        "file_type": extracted.file_type,
        "page_count": extracted.page_count,
        "character_count": len(text),
        "preview": text[:PREVIEW_CHARS],
        "truncated": len(text) > PREVIEW_CHARS,
        "warnings": extracted.warnings,
    }


@router.post("/resume/parse", response_model=ResumeParseResult, tags=["resume"])
async def parse_resume_endpoint(file: UploadFile = File(...)) -> ResumeParseResult:
    """Extract text from an uploaded resume and return a parsed profile."""

    _reject_unsupported(file)
    temp_path = _save_upload_to_temp(file)
    try:
        extracted = extract_text_from_resume(temp_path)
    except ResumeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    result = parse_resume_text_to_profile(
        text=extracted.text,
        source_file_name=extracted.file_name,
        source_file_type=extracted.file_type,
    )
    # Surface extraction warnings alongside parsing warnings.
    if extracted.warnings:
        result.warnings = [*extracted.warnings, *result.warnings]
    return result
