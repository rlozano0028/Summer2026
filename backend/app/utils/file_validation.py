"""File validation helpers for resume uploads.

Centralizes the set of supported file types and the basic checks (supported
extension, non-empty) so the extractor and API layers stay consistent.
"""

from __future__ import annotations

from pathlib import Path

# Supported resume file extensions (lower-case, including the leading dot).
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx", ".txt"})


class ResumeValidationError(Exception):
    """Base class for all resume validation problems."""


class UnsupportedFileTypeError(ResumeValidationError):
    """Raised when a file has an extension we do not support."""


class EmptyFileError(ResumeValidationError):
    """Raised when a file exists but contains no bytes."""


def normalized_extension(file_path: Path) -> str:
    """Return the lower-cased file extension (including the leading dot)."""

    return file_path.suffix.lower()


def is_supported_extension(file_path: Path) -> bool:
    """Return True if the file extension is one we know how to handle."""

    return normalized_extension(file_path) in SUPPORTED_EXTENSIONS


def validate_resume_file(file_path: Path) -> None:
    """Validate that a file can be processed as a resume.

    Raises:
        UnsupportedFileTypeError: extension is not supported.
        EmptyFileError: file exists but is empty.
        FileNotFoundError: file does not exist.
    """

    if not file_path.exists():
        raise FileNotFoundError(f"Resume file not found: {file_path}")

    if not is_supported_extension(file_path):
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{normalized_extension(file_path) or '(none)'}'. "
            f"Supported types are: {supported}."
        )

    if file_path.stat().st_size == 0:
        raise EmptyFileError(
            f"The file '{file_path.name}' is empty. Please upload a resume with content."
        )
