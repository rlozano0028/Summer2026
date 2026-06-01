# Resume Autofill Assistant - Backend

Local-first personal job-application autofill assistant. This backend covers
**Phase 1** (candidate profile schema) and **Phase 2** (resume ingestion and
parsing). There is no browser automation, scraping, login automation, or
auto-submit behavior here.

## Requirements

- Python 3.10+ (developed on 3.14)

## Setup

### 1. Create and activate a virtual environment

Windows (PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -e ".[dev]"
```

This installs FastAPI, Uvicorn, Pydantic, python-multipart, PyMuPDF,
python-docx, and email-validator, plus the dev tools (pytest, httpx).

> Note: PyMuPDF and python-docx are imported lazily. If a wheel is unavailable
> for your Python version, TXT extraction and the test suite still work; PDF /
> DOCX extraction will return a clear warning until the library installs.

## Run the API locally

```bash
uvicorn app.main:app --reload
```

Then open the interactive docs at http://127.0.0.1:8000/docs.

## Run the tests

```bash
pytest
```

## Example requests

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Extract text from a resume (returns metadata + preview):

```bash
curl -X POST http://127.0.0.1:8000/resume/extract-text \
  -F "file=@/path/to/resume.pdf"
```

Parse a resume into a profile:

```bash
curl -X POST http://127.0.0.1:8000/resume/parse \
  -F "file=@/path/to/resume.docx"
```

On Windows PowerShell, use `curl.exe` (not the `curl` alias) for `-F` uploads:

```powershell
curl.exe -X POST http://127.0.0.1:8000/resume/parse -F "file=@C:\path\to\resume.txt"
```

## Project layout

```
backend/
  app/
    main.py                     FastAPI app
    models/
      candidate_profile.py      Phase 1 Pydantic schema
      resume.py                 ExtractedResumeText, ResumeParseResult
    services/
      resume_text_extractor.py  PDF/DOCX/TXT -> text
      resume_profile_parser.py  text -> rough profile (+ AI hook stub)
    api/routes/resume.py        /health, /resume/extract-text, /resume/parse
    utils/file_validation.py    extension/empty checks
  tests/                        pytest suite (offline)
  pyproject.toml
```

See [`../docs/phase-1-profile-schema.md`](../docs/phase-1-profile-schema.md) and
[`../docs/phase-2-resume-ingestion.md`](../docs/phase-2-resume-ingestion.md) for
design details.
