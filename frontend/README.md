# Autofill Assistant - Dashboard

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

## Layout

- **Header**: backend status (Connected / Offline) and profile status (No profile /
  Needs review / Reviewed). A banner with the start command appears only when the
  backend is offline.
- **Safety strip**: you submit, sensitive questions are protected, data stays local.
- **1 Upload resume**, **2 Edit profile**, **3 Review** (mark reviewed), and
  **4 Test on a sample form** (the mapping review and override editor).

Styles live in `src/index.css` (design tokens) and `src/styles/app.css`. The five
decision colors are shared with the extension popup. Grouping and confidence
levels are in `src/lib/decisions.ts`.

## Manual testing checklist

- [ ] With the backend stopped, the header says Offline and the banner shows the
      start command; **Retry** clears it once the backend is up.
- [ ] Upload a PDF/DOCX/TXT resume; click **Parse & save**. A "first draft" notice,
      any warnings, and "Not found in the resume" chips are shown.
- [ ] Edit a field and click **Save profile**; reloading the page keeps it.
- [ ] **Mark profile reviewed** turns the header chip and the step 3 badge to
      Reviewed.
- [ ] Invalid JSON in education/experience/projects shows an error and does not
      save.
- [ ] **New profile** with a profile loaded asks "Discard unsaved edits?" inline
      before clearing the editor.
- [ ] In step 4, analyze `engineering`: counts for Will fill / Suggested / Needs
      review / Protected / Skipped are shown, rows show the field's own label,
      confidence level, redacted value, and reason; **Why?** shows evidence.
- [ ] Analyze `sensitive-fields`: Will fill is 0 and every question is under
      Protected with no confidence or value shown.
- [ ] **Dry run** reports counts and says nothing was typed or submitted.
- [ ] Under **Correct a decision for this form**, save an override; the plan
      re-analyzes with it applied. Forcing Fill on a sensitive field is saved as
      Needs review.
