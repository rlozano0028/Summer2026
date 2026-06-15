# Sample forms (Phase 4)

These are **fake, local-only** HTML job-application forms used by the browser
automation prototype. They are the *only* forms the prototype is allowed to
touch in Phase 4.

## Files

- `basic-application.html` — a small form with common identity, contact, links,
  skills, a resume upload, and a short-answer textarea.
- `engineering-application.html` — a more realistic form with education,
  experience, technical skills, a resume upload, a cover letter, and several
  **sensitive / legal** fields (work authorization, sponsorship, salary, and
  EEO / demographic questions).

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
```

You can also open either file directly in a browser to inspect it by hand.
