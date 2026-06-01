# Phase 2 - Resume Ingestion and Parsing

Phase 2 turns an uploaded resume file into (1) plain text and (2) a rough
`CandidateProfile`. It is deliberately conservative: it never invents data, and
it flags everything uncertain for manual review.

## Supported file types

| Extension | Library used        | Notes                                   |
|-----------|---------------------|-----------------------------------------|
| `.pdf`    | PyMuPDF (`fitz`)    | Also reports `page_count`.              |
| `.docx`   | `python-docx`       | Reads paragraphs and table cells.       |
| `.txt`    | stdlib `pathlib`    | UTF-8 with `errors="replace"`.          |

Validation (in [`backend/app/utils/file_validation.py`](../backend/app/utils/file_validation.py)):

- Unsupported extensions raise `UnsupportedFileTypeError`.
- Empty (0-byte) files raise `EmptyFileError`.
- Missing files raise `FileNotFoundError`.

## How extraction works

`extract_text_from_resume(file_path: Path) -> ExtractedResumeText` (in
[`backend/app/services/resume_text_extractor.py`](../backend/app/services/resume_text_extractor.py))
validates the file, dispatches by extension, and returns:

- `text` - the extracted plain text
- `file_name`, `file_type`
- `page_count` - only for PDFs
- `warnings` - recoverable issues (corrupt file, image-only PDF, missing
  optional library, etc.)

PyMuPDF and python-docx are imported lazily inside their helpers. If a wheel is
not installed for your Python version, extraction for that format returns an
empty string plus a helpful warning instead of crashing the app. TXT extraction
and the entire test suite work without those libraries.

## How deterministic parsing works

`parse_resume_text_to_profile(text, source_file_name, source_file_type) -> ResumeParseResult`
(in [`backend/app/services/resume_profile_parser.py`](../backend/app/services/resume_profile_parser.py))
uses only simple, explainable rules:

- Email via regex.
- Phone via regex (US-style formats).
- LinkedIn and GitHub URLs via regex.
- Full name guessed from the top few non-empty lines (added to review notes).
- Skills via case-insensitive, boundary-aware keyword matching. Boundaries treat
  `+`, `#`, and `.` as part of a token, so `C++` and `C#` match correctly and
  `Java` does not match inside `JavaScript`.

It always sets `metadata.needs_review = True`, records uncertain items in
`warnings` / `metadata.review_notes`, lists absent fields in `missing_fields`,
and returns a rough `confidence` score in `[0.0, 1.0]`.

## What the parser intentionally does NOT do

- It does not invent schools, companies, dates, or projects.
- It does not infer work authorization, sponsorship, or salary.
- It does not auto-answer demographic, veteran, disability, or legal questions.
- It does not permanently store uploaded files.

Unknown fields are left `None` or empty by design.

## How AI extraction can be added later

`parse_with_ai(...)` in the parser module is a stub that returns `None` today
(no API key required, no network calls). A future phase can implement it to call
an LLM with a structured-output schema matching `CandidateProfile`, then fall
back to the deterministic parser when no key is configured. Sensitive fields
must still be flagged for manual review even when produced by AI.

## API endpoints

Defined in [`backend/app/api/routes/resume.py`](../backend/app/api/routes/resume.py):

- `GET /health` - returns `{"status": "ok"}`.
- `POST /resume/extract-text` - upload a file; returns metadata + a text preview.
- `POST /resume/parse` - upload a file; returns a full `ResumeParseResult`.

Uploaded files are written to a temporary path, processed, and deleted in a
`finally` block. Nothing is persisted in this phase.

## How to run the API and tests

From the `backend` directory with the virtual environment active:

```bash
# Run the API
uvicorn app.main:app --reload

# Run the tests
pytest
```

See [`backend/README.md`](../backend/README.md) for full setup instructions and
example `curl` commands.
