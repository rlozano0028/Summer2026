# Resume Autofill Assistant - Frontend (Phase 3)

A local React + TypeScript (Vite) dashboard for uploading a resume, reviewing
the parsed candidate profile, editing it, and saving it locally via the backend
API.

## Install

```bash
cd frontend
npm install
```

## Run the dev server

```bash
npm run dev
```

Open the printed URL (default http://localhost:5173). The backend must be
running separately (see `../backend/README.md`).

## Build

```bash
npm run build
```

## Environment variables

The API base URL defaults to `http://127.0.0.1:8000`. To point at a different
backend, create `frontend/.env.local`:

```
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Notes

- The Vite config intentionally does not use `@vitejs/plugin-react`, so the
  build works with the packages already installed (no extra network install).
  The dev server still works but reloads the full page on change instead of
  using React Fast Refresh. To enable HMR later: `npm install -D @vitejs/plugin-react`
  and add `react()` to `vite.config.ts`.

## Manual testing checklist

- [ ] Status banner shows "Backend connected" (start backend if not).
- [ ] Upload a PDF/DOCX/TXT resume; click "Parse & save".
- [ ] Warnings and missing fields are shown after parsing.
- [ ] Editor is populated with parsed values.
- [ ] Editing a field and clicking "Save profile" succeeds.
- [ ] Reloading the page auto-loads the saved profile.
- [ ] "Mark profile reviewed" flips the status badge and adds a review note.
- [ ] Invalid JSON in education/experience/projects shows an error and does not
      save.
- [ ] Sensitive fields (work authorization, salary) default to Unknown/blank.

## Phase 5: mapping review UI

The automation panel ("Field-mapping review") works against local sample forms
only and never submits.

### Test the mapping review UI

- [ ] Pick a sample form and click **Analyze form**.
- [ ] Decisions are grouped into **Will fill / Suggestions / Needs manual review
      / Skipped** with counts.
- [ ] Each row shows the category, action, confidence, reason, sensitive/missing
      flags, and a redacted value preview.
- [ ] Click **Show evidence** to expand the evidence list for a field.
- [ ] Analyze `sensitive-fields`: every field is manual review, fill count is 0,
      and a sensitive warning banner appears.

### Save a local mapping override

- [ ] In **Add a local mapping override**, select a detected field, pick a safe
      category and an action (`suggest` / `manual_review` / `skip` / `fill`), and
      click **Save override**.
- [ ] The plan re-analyzes with the override applied.
- [ ] Trying to force a sensitive field to `fill` is downgraded to manual review
      with a warning.

### Inspect fill / suggest / manual_review / skip decisions

- [ ] Use the grouped view and per-field reason/evidence to confirm why each
      field was filled, suggested, skipped, or flagged for manual review.

> Note: the frontend has no automated test framework configured, so these are
> manual checks. If a test runner is added later (e.g. Vitest +
> Testing Library), start with a `FieldMappingReview` rendering test.
