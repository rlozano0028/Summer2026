"""Candidate profile API routes (Phase 3).

Provides local CRUD for the single reviewed candidate profile plus a dedicated
endpoint to toggle the review status. Storage is a local JSON file (see
``app.services.profile_storage``); nothing is sent anywhere off-machine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.candidate_profile import CandidateProfile
from app.services import profile_storage

router = APIRouter(prefix="/profile", tags=["profile"])


class ReviewStatusUpdate(BaseModel):
    """Body for PATCH /profile/review-status."""

    needs_review: bool
    review_note: Optional[str] = None


class DeleteResponse(BaseModel):
    """Response for DELETE /profile."""

    deleted: bool
    message: str


@router.get("", response_model=CandidateProfile)
def get_profile() -> CandidateProfile:
    """Return the saved profile, or 404 if none has been saved yet."""

    try:
        profile = profile_storage.load_profile()
    except profile_storage.ProfileStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="No saved profile found. Upload and parse a resume, or save a profile first.",
        )
    return profile


@router.put("", response_model=CandidateProfile)
def put_profile(profile: CandidateProfile) -> CandidateProfile:
    """Save (overwrite) the profile and return what was stored."""

    return profile_storage.save_profile(profile)


@router.patch("/review-status", response_model=CandidateProfile)
def patch_review_status(update: ReviewStatusUpdate) -> CandidateProfile:
    """Update the profile's review status and optionally append a review note."""

    try:
        profile = profile_storage.load_profile()
    except profile_storage.ProfileStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="No saved profile found to update. Save a profile first.",
        )

    profile.metadata.needs_review = update.needs_review
    if update.review_note:
        timestamp = datetime.now(timezone.utc).isoformat()
        profile.metadata.review_notes.append(f"[{timestamp}] {update.review_note}")

    return profile_storage.save_profile(profile)


@router.delete("", response_model=DeleteResponse)
def delete_profile() -> DeleteResponse:
    """Delete the saved profile if present."""

    deleted = profile_storage.delete_profile()
    if deleted:
        return DeleteResponse(deleted=True, message="Saved profile deleted.")
    return DeleteResponse(deleted=False, message="No saved profile to delete.")
