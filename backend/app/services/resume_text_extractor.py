"""Resume text extraction (Phase 2).

Extracts plain text from PDF, DOCX, and TXT resumes. The heavy third-party
libraries (PyMuPDF/``fitz`` and ``python-docx``) are imported lazily inside the
format-specific helpers. This keeps the module importable - and TXT extraction
plus the whole test suite working - even on environments where those wheels are
not installed yet.
"""

from __future__ import annotations

from pathlib import Path

from app.models.resume import ExtractedResumeText
from app.utils.file_validation import normalized_extension, validate_resume_file


def extract_text_from_resume(file_path: Path) -> ExtractedResumeText:
    """Extract text from a resume file.

    Args:
        file_path: Path to a ``.pdf``, ``.docx``, or ``.txt`` file.

    Returns:
        An :class:`ExtractedResumeText` with the text and light metadata.
        Recoverable problems are reported in ``warnings`` rather than raised.

    Raises:
        UnsupportedFileTypeError: extension not supported.
        EmptyFileError: file is empty.
        FileNotFoundError: file does not exist.
    """

    file_path = Path(file_path)
    validate_resume_file(file_path)

    extension = normalized_extension(file_path)
    file_name = file_path.name

    if extension == ".txt":
        return _extract_txt(file_path, file_name)
    if extension == ".pdf":
        return _extract_pdf(file_path, file_name)
    if extension == ".docx":
        return _extract_docx(file_path, file_name)

    # validate_resume_file already guards this, but keep the branch explicit.
    raise AssertionError(f"Unhandled supported extension: {extension}")


def _extract_txt(file_path: Path, file_name: str) -> ExtractedResumeText:
    """Read a plain-text resume, replacing undecodable bytes."""

    warnings: list[str] = []
    text = ""
    try:
        # ``errors="replace"`` keeps decoding from blowing up on odd encodings.
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        warnings.append(f"Could not read text file: {exc}")

    if not text.strip():
        warnings.append("No readable text found in the file.")

    return ExtractedResumeText(
        text=text,
        file_name=file_name,
        file_type="txt",
        page_count=None,
        warnings=warnings,
    )


def _extract_pdf(file_path: Path, file_name: str) -> ExtractedResumeText:
    """Extract text from a PDF using PyMuPDF (``fitz``)."""

    warnings: list[str] = []

    try:
        import fitz  # type: ignore  # PyMuPDF, imported lazily.
    except ImportError:
        return ExtractedResumeText(
            text="",
            file_name=file_name,
            file_type="pdf",
            page_count=None,
            warnings=[
                "PyMuPDF (pymupdf) is not installed, so PDF text could not be "
                "extracted. Install it with 'pip install pymupdf'."
            ],
        )

    text_parts: list[str] = []
    page_count: int | None = None
    try:
        with fitz.open(file_path) as doc:
            page_count = doc.page_count
            for page in doc:
                text_parts.append(page.get_text())
    except Exception as exc:  # noqa: BLE001 - surface any parse failure as a warning.
        warnings.append(
            f"The PDF could not be fully read (it may be corrupted or "
            f"image-only): {exc}"
        )

    text = "\n".join(text_parts)
    if not text.strip():
        warnings.append(
            "No selectable text found in the PDF. It may be a scanned/image "
            "document that needs OCR."
        )

    return ExtractedResumeText(
        text=text,
        file_name=file_name,
        file_type="pdf",
        page_count=page_count,
        warnings=warnings,
    )


def _extract_docx(file_path: Path, file_name: str) -> ExtractedResumeText:
    """Extract text from a DOCX using python-docx."""

    warnings: list[str] = []

    try:
        import docx  # type: ignore  # python-docx, imported lazily.
    except ImportError:
        return ExtractedResumeText(
            text="",
            file_name=file_name,
            file_type="docx",
            page_count=None,
            warnings=[
                "python-docx is not installed, so DOCX text could not be "
                "extracted. Install it with 'pip install python-docx'."
            ],
        )

    text = ""
    try:
        document = docx.Document(str(file_path))
        paragraphs = [paragraph.text for paragraph in document.paragraphs]
        # Include table cell text, which holds content in many resume templates.
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text:
                        paragraphs.append(cell.text)
        text = "\n".join(paragraphs)
    except Exception as exc:  # noqa: BLE001 - surface any parse failure as a warning.
        warnings.append(
            f"The DOCX could not be read (it may be corrupted or not a valid "
            f"Word document): {exc}"
        )

    if not text.strip():
        warnings.append("No readable text found in the DOCX file.")

    return ExtractedResumeText(
        text=text,
        file_name=file_name,
        file_type="docx",
        page_count=None,
        warnings=warnings,
    )
