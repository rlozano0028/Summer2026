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
- **Phase 6** - A Chrome extension prototype that reads the form on the current
  page, gets a plan from the local backend using the Phase 5 engine, shows it for
  review, and fills only approved safe fields - local sample forms only, never
  submits. See
  [docs/phase-6-chrome-extension-integration.md](docs/phase-6-chrome-extension-integration.md).
- **Phase 7** - Controlled support for real application pages: a backend URL
  allow-list plus safety policy, per-platform metadata adapters for Greenhouse,
  Lever, Ashby, Workday, and SmartRecruiters, and a required per-page
  confirmation. Still user-activated only, still never submits, still never fills
  sensitive fields. See
  [docs/phase-7-real-application-platforms.md](docs/phase-7-real-application-platforms.md)
  and [docs/platform-support-matrix.md](docs/platform-support-matrix.md).

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

## Chrome extension (Phase 6)

With the backend running, build the extension and load it into Chrome:

```bash
cd extension
npm install
npm run build
```

Then open `chrome://extensions`, enable **Developer mode**, click
**Load unpacked**, and select `extension/dist`.

The backend also serves the sample forms over http so the extension can work on
them, for example
<http://127.0.0.1:8000/sample-forms/basic-application.html>. Open one, click the
extension icon, then use **Detect fields** → **Analyze with local profile** →
**Highlight decisions** → **Apply safe fills**.

The extension never submits a form, never clicks a button, and never fills
sensitive/legal fields, passwords, or file uploads. Details and troubleshooting are
in [extension/README.md](extension/README.md).

## Real application pages (Phase 7)

The same extension also works on a real application page you opened yourself, on
Greenhouse, Lever, Ashby, Workday, or SmartRecruiters over `https`. Open the page,
click the extension icon, read the warning, tick the confirmation, then use the
same Detect → Analyze → Highlight → Apply flow. The confirmation is required on
every page and resets whenever the popup closes.

Company-hosted forms are opt-in per host via the backend environment variable
`PHASE7_APPROVED_DOMAINS`, which takes effect on restart:

```powershell
$env:PHASE7_APPROVED_DOMAINS = "careers.acme-corp.example"
uvicorn app.main:app --reload
```

To try the platform adapters without touching a real site, the backend serves six
synthetic fixture pages, for example
<http://127.0.0.1:8000/test-fixtures/platform-pages/workday-like.html>.

Phase 7 needs **no new browser permission**: `activeTab` plus `scripting` covers
one tab, only after you click, so nothing runs on a page you did not activate.
Custom controls such as Workday's dropdowns are always routed to manual review
rather than filled.

## Run the checks

```bash
# Backend tests (from backend/, venv active)
pytest

# Frontend build (from frontend/)
npm run build

# Extension typecheck, tests, build (from extension/)
npm run typecheck
npm test
npm run build
```

## Privacy

- Uploaded resume files are never stored permanently.
- Only the reviewed profile JSON is saved locally (git-ignored).
- No cloud storage, no analytics, no third-party calls, no API keys required.
- The Chrome extension sends only field metadata to the local backend - never page
  values, page HTML, screenshots, or passwords - and stores no profile data in
  Chrome. `chrome.storage.local` holds the backend URL and nothing else.
- On real pages the backend evaluates the URL string against a local allow-list. It
  never fetches the page, and it runs no browser.
- There is no scraping, mass applying, navigation, login automation, captcha
  handling, auto-submit, or generated answers anywhere in this project, and none is
  planned.
