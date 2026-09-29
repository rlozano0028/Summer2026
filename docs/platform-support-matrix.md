# Platform support matrix

What the extension does and does not do on each supported platform, as of Phase 7.

"Supported" here is a narrow claim: the extension will read the fields on a page you
opened, ask the local backend for a plan, show it to you, and fill the plain fields
you approve. It never submits, never clicks Apply or Next, and never answers a
question that could matter legally.

## Platforms

| Platform | Host patterns | Confirmation required | Standard inputs | Custom controls | Risk |
| --- | --- | --- | --- | --- | --- |
| Local sample form | the six loopback origins | no | yes | flagged, never filled | low |
| Greenhouse | `.greenhouse.io` | yes | yes | flagged, never filled | medium |
| Lever | `.lever.co` | yes | yes | flagged, never filled | medium |
| Ashby | `.ashbyhq.com` | yes | yes | flagged, never filled | medium |
| Workday | `.myworkdayjobs.com`, `.myworkdaysite.com` | yes | yes | flagged, never filled | high |
| SmartRecruiters | `.smartrecruiters.com` | yes | yes | flagged, never filled | high |
| Company-hosted (`generic`) | none by default; opt in per host | yes | yes | flagged, never filled | high |

A leading dot means "this host or any subdomain of it", matched on label boundaries.
`boards.greenhouse.io` matches; `boards.greenhouse.io.evil.example` does not. Every
real platform must be served over `https`; only loopback pages may use `http`.

Company domains are not matched by any pattern. Add a specific host to the backend's
`PHASE7_APPROVED_DOMAINS` environment variable and restart:

```powershell
$env:PHASE7_APPROVED_DOMAINS = "careers.acme-corp.example"
uvicorn app.main:app --reload
```

Approval is per host, not per domain tree: approving `acme-corp.example` does not
approve `careers.acme-corp.example`.

## What is never filled, on any platform

| Field kind | Why |
| --- | --- |
| Passwords | Never read, never sent, skipped before any metadata is collected. |
| File uploads / resume attachments | The extension cannot and will not attach a file. |
| Submit, Apply, Next, Back, Save | Never clicked. Not even to advance a wizard. |
| Work authorization, sponsorship | Legal answers. Yours to give. |
| Salary and compensation expectations | A negotiation, not a data field. |
| Demographic, disability, veteran status | Voluntary self-identification. Yours alone. |
| Legal acknowledgments and certifications | You are the one certifying. |
| Criminal history | Yours alone. |
| Checkboxes and radio buttons | Never toggled, on any platform. |
| Custom controls (see below) | Cannot be set correctly, so not attempted. |
| Long-form essays and cover letters | Not generated, not tailored, not written. |

## Custom controls

A "custom control" is anything that looks like an input but is not one: an ARIA
combobox, a `role="listbox"` picker, a contenteditable rich-text box, a framework-owned
dropdown built from divs. The value of such a control lives in JavaScript state that
the DOM does not expose, so writing to the element either does nothing or corrupts the
page's own state.

These are detected, flagged, reported in the plan as **Not supported**, and left
alone. Workday and SmartRecruiters use them heavily, which is why both are marked
high risk.

## Per-platform notes

**Greenhouse.** The easiest case: native inputs with real `<label for=...>` elements.
Custom questions are named by index (`job_application[answers_attributes][3][...]`), so
the adapter falls back to the wrapper text for those. Company career sites often embed
the form in an iframe; the extension only sees the frame it is running in and tells you
when frames are present.

**Lever.** Native inputs with `data-qa` attributes. The `urls[LinkedIn]` naming
convention makes link fields unambiguous. Custom question sections use
`cards[<section>][fieldN]` and fall back to wrapper text.

**Ashby.** React-controlled inputs with hashed class names, so class names are ignored
as evidence. Filling goes through the prototype value setter and dispatches
`input`/`change`/`blur`, which is what React needs to notice. Long answers are often
rich-text editors and are left to you.

**Workday.** The hardest platform, and the one where the extension does least.
`data-automation-id` is the only reliable identifier and is used as the primary label
source. Country, state, and skills are custom widgets. The form is a multi-step
wizard: only the step currently on screen is analyzed, and the extension never advances
it. Expect most of a Workday form to be marked manual review or not supported.

**SmartRecruiters.** `data-test` attributes are used for both selectors and labels.
Location is an autocomplete widget and is left to you. Form sections appear as you
scroll, so click Scan again after more of the form is rendered.

**Company-hosted forms.** No assumptions beyond ordinary HTML. Because these vary
without limit, the adapter is conservative and every field deserves a look before you
submit.

## How a page is decided

Two separate questions, answered by two separate mechanisms:

1. **May this page be analyzed?** Decided from the URL, by the backend, on every
   request. Fails closed: anything not explicitly recognized is refused.
2. **How should this page be read?** Decided from DOM signals, by the extension,
   choosing an adapter.

They are allowed to disagree, and the disagreement is recorded rather than resolved.
That separation is what lets the synthetic fixtures work: a Greenhouse-shaped fixture
served from `127.0.0.1` is a `local` page for safety purposes while still being read by
the Greenhouse adapter.
