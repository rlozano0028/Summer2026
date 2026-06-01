"""Tests for the Phase 2 resume text extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.resume_text_extractor import extract_text_from_resume
from app.utils.file_validation import EmptyFileError, UnsupportedFileTypeError


def test_unsupported_extension_is_rejected(tmp_path: Path) -> None:
    """A file with an unsupported extension raises UnsupportedFileTypeError."""

    bad = tmp_path / "resume.rtf"
    bad.write_text("some content", encoding="utf-8")

    with pytest.raises(UnsupportedFileTypeError):
        extract_text_from_resume(bad)


def test_empty_file_is_rejected(tmp_path: Path) -> None:
    """An empty (0-byte) file raises EmptyFileError."""

    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")

    with pytest.raises(EmptyFileError):
        extract_text_from_resume(empty)


def test_txt_extraction_returns_text_and_type(tmp_path: Path) -> None:
    """A simple TXT resume is read back with the correct metadata."""

    content = "Jane Doe\njane@example.com\nPython developer"
    txt = tmp_path / "resume.txt"
    txt.write_text(content, encoding="utf-8")

    result = extract_text_from_resume(txt)

    assert result.file_type == "txt"
    assert result.file_name == "resume.txt"
    assert "Jane Doe" in result.text
    assert result.page_count is None
    assert result.warnings == []
