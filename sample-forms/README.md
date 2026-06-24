# Sample forms (Phase 4 + Phase 5)

These are **fake, local-only** HTML job-application forms used by the browser
automation prototype and the Phase 5 field-mapping engine. They are the *only*
forms the prototype is allowed to touch.

## Files

- `basic-application.html` — a small form with common identity, contact, links,
  skills, a resume upload, and a short-answer textarea.
- `engineering-application.html` — a more realistic form with education,
  experience, technical skills, a resume upload, a cover letter, and several
  **sensitive / legal** fields (work authorization, sponsorship, salary, and
  EEO / demographic questions).
- `edge-case-labels.html` (Phase 5) — tricky label associations: labels wrapping
  inputs, `label for=`, aria-label only, placeholder only, camelCase/snake_case
  names, hyphenated ids, nearby text without an explicit label, similar fields,
  and disabled/readonly/hidden/submit controls.
  - Expected: clear identity/skill fields fill or suggest; disabled/readonly/
    hidden/submit are skipped; ambiguous ones go to manual review.
- `sensitive-fields.html` (Phase 5) — only sensitive/legal fields (work
  authorization, sponsorship, salary, veteran, disability, race/ethnicity,
  gender, criminal history, date of birth, SSN, legal acknowledgment).
  - Expected: **every** field is manual review (or skip). Nothing is ever
    filled.
- `select-radio-checkboxes.html` (Phase 5) — country/state/remote selects, a
  non-sensitive checkbox, a sensitive checkbox, a non-sensitive radio group, and
  a sensitive sponsorship radio group.
  - Expected: selects fill only on an exact option match (else suggest);
    checkboxes/radios are conservative manual review; sensitive ones are always
    manual review.

## Important

- These forms are not connected to any server. **Nothing is ever submitted.**
- The submit button is `disabled` and each form also uses `onsubmit="return false"`
  as a second guard.
- Sensitive / legal fields are intentionally included so the prototype can prove
  it detects them and leaves them for **manual review** instead of autofilling.

## How to use them

Run the CLI demo from the `backend/` directory (with the virtual environment
activated and a reviewed profile saved):

```bash
python -m app.scripts.run_local_autofill_demo --form basic --dry-run
python -m app.scripts.run_local_autofill_demo --form basic --headful
python -m app.scripts.run_local_autofill_demo --form engineering --headful
python -m app.scripts.run_local_autofill_demo --form edge-case-labels --dry-run
python -m app.scripts.run_local_autofill_demo --form sensitive-fields --dry-run
python -m app.scripts.run_local_autofill_demo --form select-radio-checkboxes --dry-run
```

You can also open either file directly in a browser to inspect it by hand.
