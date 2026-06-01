"""Models describing resume ingestion results (Phase 2)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.candidate_profile import CandidateProfile


class ExtractedResumeText(BaseModel):
    """Raw text extracted from a resume file plus light metadata."""

    text: str
    file_name: str
    file_type: str
    # Only populated for PDFs; None for other formats.
    page_count: Optional[int] = None
    warnings: list[str] = Field(default_factory=list)


class ResumeParseResult(BaseModel):
    """Result of turning extracted resume text into a structured profile."""

    raw_text: str
    profile: CandidateProfile
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    # Rough 0.0-1.0 confidence in the deterministic extraction.
    confidence: float = 0.0
    source_file_name: str
    source_file_type: str
