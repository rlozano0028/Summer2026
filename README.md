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

## Privacy

- Uploaded resume files are never stored permanently.
- Only the reviewed profile JSON is saved locally (git-ignored).
- No cloud storage, no analytics, no third-party calls, no API keys required.
