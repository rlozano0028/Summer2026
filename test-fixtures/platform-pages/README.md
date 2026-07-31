# Synthetic platform fixture pages

Six hand-written HTML pages used to exercise the Phase 7 platform adapters without
touching a real job site.

**These are not copies of any real page.** Nothing here was scraped, downloaded, or
mirrored. Each file was written by hand to imitate the *structural signals* a real
applicant tracking system tends to expose — attribute naming conventions, wrapper
ids, and the presence of custom controls — because those signals are what the
adapters key off. Field labels are generic wording, not vendor copy.

| File | Imitates | Signals it carries |
| --- | --- | --- |
| `greenhouse-like.html` | Greenhouse | `#application_form`, `job_application[...]` field names |
| `lever-like.html` | Lever | `data-qa` attributes, `urls[...]` / `cards[...]` names |
| `ashby-like.html` | Ashby | `#ashby-application-form-container`, hashed `_class_` names, contenteditable answer |
| `workday-like.html` | Workday | `data-automation-id` throughout, several custom dropdowns, wizard footer |
| `smartrecruiters-like.html` | SmartRecruiters | `data-test` attributes, `#st-application`, custom location picker |
| `generic-company-like.html` | A plain company careers form | no ATS markers at all, plus a hidden input |

Every page:

- has `onsubmit="return false"` and a **disabled** submit button, so it cannot
  submit even by accident;
- posts to nowhere (no `action` attribute, no script that navigates);
- contains contact fields, links, skills, education, experience, a short answer, a
  resume upload, sponsorship and work-authorization questions, a salary question,
  voluntary EEO-style questions, and a legal acknowledgment checkbox.

The last group matters more than the first: these are the fields the extension must
*refuse* to fill. A fixture that only had name and email would not prove anything.

## Serving them

The backend mounts this directory read-only:

```
uvicorn app.main:app --reload     # from backend/
```

then open `http://127.0.0.1:8000/test-fixtures/platform-pages/workday-like.html`.

Because that URL is a loopback origin, the safety layer classifies the page as
`local` and the extension needs no real-page confirmation, exactly as in Phase 6.
The *adapter* is still chosen from the DOM signals, so this is how platform-specific
metadata extraction gets exercised without a real site being involved.

## Adding a fixture

Keep it synthetic and keep it inert: hand-write the markup, disable the submit
button, add `onsubmit="return false"`, and include at least one sensitive question
so the refusals stay under test. Do not paste markup copied from a live posting.
