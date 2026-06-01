# Phase 3 - Local Dashboard and Profile Review UI

## What Phase 3 adds

Phase 3 turns the Phase 1-2 backend into a usable local tool:

- A **profile storage service** that saves one reviewed candidate profile as a
  local JSON file.
- **Profile API routes** to read, save, review-toggle, and delete that profile.
- A **`/resume/parse-and-save`** endpoint that parses a resume and persists the
  resulting profile in one step.
- **CORS** for the local Vite dev server.
- A **React + TypeScript dashboard** (Vite) to upload a resume, review/edit the
  parsed profile, save it, and track its review status.

Nothing in this phase performs browser automation, scraping, login, or
auto-submit. There is no AI/API-key requirement.

## How the local dashboard works

The dashboard has five components:

- `StatusBanner` - pings `GET /health` and shows backend connectivity.
- `ResumeUpload` - uploads a PDF/DOCX/TXT to `POST /resume/parse-and-save`,
  showing warnings, missing fields, and a text preview.
- `ProfileEditor` - edits identity, links, skills, work authorization
  (sensitive), preferences, and education/experience/projects (validated JSON
  textareas). Saving calls `PUT /profile`.
- `ProfileSummary` - a quick read-only snapshot, including review status.
- `ReviewPanel` - shows review notes/warnings and toggles review status via
  `PATCH /profile/review-status`.

On load, the dashboard calls `GET /profile`; if a saved profile exists it is
loaded into the editor, otherwise the editor waits for an upload.

## How to run the backend

From `backend/` with the virtual environment active:

```bash
uvicorn app.main:app --reload
```

CORS is enabled for `http://localhost:5173` and `http://127.0.0.1:5173` only.
This is for local development; do not broaden it for any real deployment.

## How to run the frontend

From `frontend/`:

```bash
npm install   # first time only
npm run dev
```

Then open the printed URL (default http://localhost:5173). Override the backend
URL with `VITE_API_BASE_URL` if needed (see `frontend/README.md`).

> Note: the Vite config intentionally omits `@vitejs/plugin-react` so the build
> works offline with the packages already present. The dev server still works
> but does a full reload on change instead of React Fast Refresh. Install
> `@vitejs/plugin-react` and add it to `vite.config.ts` later if you want HMR.

## How profile JSON storage works

- Implemented in [`backend/app/services/profile_storage.py`](../backend/app/services/profile_storage.py).
- Default location: `backend/app/data/profile.json`.
- Override with the `PROFILE_STORAGE_PATH` environment variable (used by tests
  to write to a temp path).
- `save_profile`, `load_profile`, `profile_exists`, `delete_profile`, and
  `get_profile_storage_path` are the public functions.
- The file is pretty-printed JSON produced from the `CandidateProfile` model.

## What data is stored and what is NOT

Stored:

- The single reviewed/parsed candidate profile, as `profile.json`, locally.

Not stored:

- Uploaded resume files. They are written to a temp path, parsed, and deleted.
- Nothing is sent to any cloud service or third party. No analytics. No API keys.

`profile.json` is git-ignored. Treat it as sensitive personal data.

## How to manually test the flow

1. Start the backend (`uvicorn app.main:app --reload`).
2. Start the frontend (`npm run dev`) and open it in the browser.
3. Confirm the status banner shows "Backend connected".
4. Upload a small TXT/PDF/DOCX resume and click **Parse & save**.
5. Confirm warnings/missing fields appear and the editor fills with parsed data.
6. Edit a few fields (for example fix the name or add skills) and click
   **Save profile**.
7. Reload the page and confirm the saved profile loads automatically.
8. In the Review panel, click **Mark profile reviewed** and confirm the status
   badge changes and a review note is added.
9. Optionally verify `backend/app/data/profile.json` exists and contains your
   profile.

## Why the profile still requires human review

The deterministic parser only detects simple fields and never invents data, so
parsed profiles are drafts. Sensitive/legal fields (work authorization,
sponsorship, salary, demographic, veteran, disability, criminal-history) are
never auto-answered and must be confirmed by you. The profile stays
`needs_review = true` until you explicitly mark it reviewed in the dashboard.

## What should come next in Phase 4

- A browser-automation layer (or Chrome extension) that consumes the
  **reviewed** profile to assist with filling job-application forms.
- A guard so automation refuses to run while `needs_review` is true.
- Field-level mapping from profile data to common application form fields, with
  explicit user confirmation for sensitive questions and no auto-submit.
