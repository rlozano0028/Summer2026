# Summer2026

Personal resume assistant
Made by Juan Jiminez
Made by  Roman Lozano

A local-first, personal job-application autofill assistant. All data stays on
your machine.

## Phases

- **Phase 1** - Candidate profile schema (Pydantic). See
  [docs/phase-1-profile-schema.md](docs/phase-1-profile-schema.md).
- **Phase 2** - Resume ingestion + parsing (PDF/DOCX/TXT). See
  [docs/phase-2-resume-ingestion.md](docs/phase-2-resume-ingestion.md).
- **Phase 3** - Local dashboard to upload, review, edit, and save the profile.
  See [docs/phase-3-local-dashboard.md](docs/phase-3-local-dashboard.md).
- **Phase 4** - Local-only browser-automation prototype (Playwright) that fills
  sample forms from the saved profile, never submits, and leaves sensitive/legal
  fields for manual review. See
  [docs/phase-4-browser-automation-prototype.md](docs/phase-4-browser-automation-prototype.md).
- **Phase 5** - An explainable, testable field-mapping engine: enriched field
  context, evidence-based classification + confidence, aggressive sensitive-field
  detection, redacted value resolution, and local user-controlled mapping
  overrides - still local sample forms only, still never submits. See
  [docs/phase-5-field-mapping-engine.md](docs/phase-5-field-mapping-engine.md).

## Run it locally

Backend (FastAPI):

```bash
cd backend
python -m venv .venv
# Windows:    .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Frontend (React + Vite), in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the frontend URL (default http://localhost:5173) with the backend running.

## Browser automation prototype (Phase 4)

Install the Playwright browser once, then run the local demo (from `backend/`,
with a saved profile):

```bash
python -m playwright install chromium
python -m app.scripts.run_local_autofill_demo --form basic --dry-run
python -m app.scripts.run_local_autofill_demo --form engineering --headful
```

This only fills the local sample forms in `sample-forms/`. It never targets real
job sites and never submits.

## Field-mapping engine (Phase 5)

Phase 5 adds an explainable mapping engine and local mapping overrides. Analyze
any of the five local sample forms (`basic`, `engineering`, `edge-case-labels`,
`sensitive-fields`, `select-radio-checkboxes`) from the dashboard or CLI, review
the grouped decisions with evidence, and pin per-field overrides locally.

Run the checks:

```bash
# Backend tests (from backend/, venv active)
pytest

# Frontend build (from frontend/)
npm run build
```

## Privacy

- Uploaded resume files are never stored permanently.
- Only the reviewed profile JSON is saved locally (git-ignored).
- No cloud storage, no analytics, no third-party calls, no API keys required.
