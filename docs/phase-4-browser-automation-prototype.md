# Phase 4: Browser Automation Prototype (Playwright)

Phase 4 proves that the app can take a **reviewed, saved candidate profile**
(from Phase 3) and use it to fill out **local sample job-application forms** with
Playwright. It is a prototype: deterministic, privacy-conscious, and deliberately
narrow in scope.

## What Phase 4 adds

- Automation Pydantic models (`app/models/automation.py`).
- Two local sample forms (`sample-forms/`).
- Playwright-based field detection (`app/services/form_field_detector.py`).
- A deterministic field mapper (`app/services/field_mapper.py`).
- A Playwright autofill runner (`app/services/playwright_autofill.py`).
- Redacted JSON report storage (`app/services/automation_report_storage.py`).
- A CLI demo (`app/scripts/run_local_autofill_demo.py`).
- FastAPI routes (`app/api/routes/automation.py`).
- A React panel (`frontend/src/components/AutomationPrototype.tsx`).

## Why automation is limited to local sample forms

This phase intentionally does **not**:

- automate or scrape real job sites,
- log into websites or bypass captchas,
- auto-submit applications or do mass-apply,
- use AI to answer questions,
- fill sensitive/legal fields automatically.

The only forms it will open are the approved local files in `sample-forms/`,
referenced by `file://` URLs. No endpoint or CLI flag accepts an arbitrary URL.

## How field detection works

`detect_form_fields(page)` runs a self-contained JavaScript snippet inside the
page (`DETECT_FIELDS_JS`). For every `input`, `textarea`, `select`, and `button`
it collects: tag, type, name, id, placeholder, aria-label, autocomplete, label
text (`label[for]` and wrapping `<label>`), nearby container text, select
options, the `required`/`visible`/`disabled`/`readonly` flags, whether it is a
file upload or submit control, and a stable CSS selector.

Selector priority: `#id` -> `[name="..."]` -> `[data-testid]` -> an
`nth-of-type` path fallback. Index-based fallbacks are only as stable as the DOM,
but we detect and fill in the same session, so this is safe for the local forms.

## How deterministic mapping works

`map_field_to_profile(field, profile)` is rule-based and explainable (no AI). It
builds a lowercase "haystack" from the field's text metadata and matches it
against ordered keyword rules. Each detected field becomes a `FieldMapping` with
an `action`, `confidence`, `reason`, and `sensitive`/`missing_value` flags.

Mapping highlights:

- Identity, links, and skills -> high confidence.
- City/state/country -> high confidence.
- Education and experience -> `suggest` (never auto-filled in this phase).
- Resume/CV upload -> `manual_review` unless an explicit resume file is provided.
- Cover letters / essays / any textarea -> `manual_review`.

## Confidence thresholds

- `fill` when confidence >= **0.90**, the value exists, the field is not
  sensitive, and it is not disabled/readonly.
- `suggest` when confidence is **0.60-0.90**.
- `manual_review` when sensitive, ambiguous, missing a value, a free-text
  answer, a resume upload without an explicit file, or an unsupported type.
- `skip` for submit buttons, disabled/hidden fields, and unknown controls.

The mapper never invents data: if the profile has no value, the field is marked
`missing_value=True` and routed to `manual_review`.

## What gets autofilled vs. what requires manual review

Autofilled (high confidence, present, non-sensitive): first/last/full name,
email, phone, city, state, country, LinkedIn, GitHub, portfolio, and skills.

Always manual review: resume/file uploads (unless an explicit resume path is
given), cover letters/essays, education/experience details, and **all sensitive
/ legal fields**.

## Why sensitive/legal fields are never auto-filled

Work authorization, sponsorship/visa, salary expectation, EEO/demographic
questions, disability, veteran status, criminal history, and legal
acknowledgments are detected and marked `sensitive=True` + `manual_review`. These
require a human decision and must never be answered automatically.

## How to run the CLI demo

From the `backend/` directory with the virtual environment activated and a saved
profile:

```bash
python -m app.scripts.run_local_autofill_demo --form basic --dry-run
python -m app.scripts.run_local_autofill_demo --form basic --headful
python -m app.scripts.run_local_autofill_demo --form engineering --headful
python -m app.scripts.run_local_autofill_demo --form engineering --headful \
    --resume-file "path/to/resume.pdf"
```

If no profile is saved, the CLI prints a message telling you to upload/review/save
one first.

## How to run the FastAPI analysis endpoint

```bash
uvicorn app.main:app --reload   # from backend/
```

- `GET /automation/sample-forms` -> `{"forms": ["basic", "engineering"]}`
- `POST /automation/analyze` `{"form_name": "basic"}` -> a `FillPlan` (no filling)
- `POST /automation/dry-run` `{"form_name": "basic"}` -> an `AutofillResult` (types nothing)
- `POST /automation/run-sample` `{"form_name": "basic", "headless": true}` -> an `AutofillResult`

The API runs headless, keeps browsers short-lived, and never submits. For headful
demos, use the CLI.

## How to use the frontend Automation Prototype panel

Start the backend and the Vite dev server, open the dashboard, and scroll to
**Automation prototype (Phase 4)**. Pick `basic` or `engineering`, then:

- **Analyze form** shows the full fill plan (action, confidence, reason, and
  sensitive/missing flags) plus counts.
- **Run dry run** runs a no-type pass and shows result counts and the report path.

The panel reminds you that real job sites are not supported in this phase.

## How reports are stored and redacted

`run_local_autofill` saves an `AutofillResult` as JSON under
`backend/app/data/automation-reports/`. Reports contain only field
labels/identifiers, actions, warnings, and timestamps - never full profile
values or resume text. `value_preview` in a plan is masked/truncated (e.g.
`a***@example.com`). The reports directory is git-ignored (the `.gitkeep` is
kept).

## Known limitations

- Index-based selectors can go stale if a page mutates between detection and fill
  (not an issue for the local forms, which are detected and filled in one session).
- Checkboxes and radio groups are conservatively deferred to manual review.
- Select elements are only changed on a confident, normalized option match.
- The mapper uses keyword matching, so unusual field labels may fall through to
  `manual_review` ("no deterministic mapping").

## What should come next in Phase 5

- A trusted, user-driven Chrome extension that reuses these deterministic
  mappings on a page the user is actively viewing (still no auto-submit).
- Optional, clearly-labeled AI assistance for free-text answers, gated behind
  explicit user review.
- Smarter, more resilient field matching and per-site mapping overrides.
