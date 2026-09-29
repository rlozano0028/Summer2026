# Autofill Assistant - Chrome extension

A Manifest V3 extension that asks the local FastAPI backend how to fill the form on
the current page, shows you the plan, and fills only the fields you approve.

**Nothing is ever submitted, and no button is ever clicked.** Local sample forms work
out of the box; real application pages work on supported platforms, only on a page you
opened yourself, and only after you confirm.

- Phase 6 design and privacy model:
  [../docs/phase-6-chrome-extension-integration.md](../docs/phase-6-chrome-extension-integration.md)
- Phase 7 real-platform support:
  [../docs/phase-7-real-application-platforms.md](../docs/phase-7-real-application-platforms.md)
- Per-platform behaviour: [../docs/platform-support-matrix.md](../docs/platform-support-matrix.md)

## Setup

```bash
cd extension
npm install
```

## Build

```bash
npm run build
```

Output goes to `extension/dist/`, which is the folder you load into Chrome. The
build runs in two passes:

- `vite build` compiles the React popup and copies `public/manifest.json` to the
  dist root.
- `node scripts/build-scripts.mjs` bundles the content script and service worker
  with esbuild as **IIFE**. This second pass is necessary because Manifest V3 will
  not load a content script containing bare ES module imports.

Other scripts:

| Command | Purpose |
| --- | --- |
| `npm run typecheck` | `tsc --noEmit` over `src/` |
| `npm test` | vitest + jsdom specs for the safety-critical helpers |
| `npm run test:watch` | the same specs in watch mode |
| `npm run clean` | delete `dist/` |

The tests use their own `vitest.config.ts` so the popup's `vite.config.ts` stays a pure
build config. They cover the URL rules, platform detection, field detection, the
filler's refusals, the highlighter, and the manifest's permissions - the places where a
mistake would mean touching something on a real page that should not be touched.

There is no watch mode. Chrome requires a manual extension reload after every
build anyway, so a watcher would save little; also, `vite build` empties `dist/`
first, which would wipe the esbuild output of a partial rebuild.

## Load the unpacked extension

1. Open `chrome://extensions`.
2. Enable **Developer mode** (top right).
3. Click **Load unpacked**.
4. Select the `extension/dist` folder (not `extension/`).

## Reload after code changes

```bash
npm run build
```

Then click the reload icon on the extension's card in `chrome://extensions`, and
**reload the sample form tab too**. The content script is injected at page load, so
an already-open tab still runs the previous version.

## Required backend

The extension expects the local FastAPI backend at **`http://127.0.0.1:8000`**:

```bash
cd backend
.venv\Scripts\activate        # Windows; source .venv/bin/activate elsewhere
uvicorn app.main:app --reload
```

You also need a saved profile. Create one in the dashboard (`frontend/`) or via
`PUT /profile`. The popup tells you if one is missing or still needs review.

The backend URL is the only thing this extension stores (in
`chrome.storage.local`). Profile data is never stored.

## Supported page URLs

### Local pages

These six origins are always in scope, need no confirmation, and are the ones the
manifest grants host permissions for:

```
http://127.0.0.1:8000    http://localhost:8000
http://127.0.0.1:5173    http://localhost:5173
http://127.0.0.1:8080    http://localhost:8080
```

The backend serves the repo's sample forms, so these work out of the box:

- <http://127.0.0.1:8000/sample-forms/basic-application.html>
- <http://127.0.0.1:8000/sample-forms/engineering-application.html>
- <http://127.0.0.1:8000/sample-forms/edge-case-labels.html>
- <http://127.0.0.1:8000/sample-forms/sensitive-fields.html>
- <http://127.0.0.1:8000/sample-forms/select-radio-checkboxes.html>

It also serves the six synthetic platform fixtures, which imitate the structure of each
supported ATS without being copies of anything real:

- <http://127.0.0.1:8000/test-fixtures/platform-pages/greenhouse-like.html>
- <http://127.0.0.1:8000/test-fixtures/platform-pages/lever-like.html>
- <http://127.0.0.1:8000/test-fixtures/platform-pages/ashby-like.html>
- <http://127.0.0.1:8000/test-fixtures/platform-pages/workday-like.html>
- <http://127.0.0.1:8000/test-fixtures/platform-pages/smartrecruiters-like.html>
- <http://127.0.0.1:8000/test-fixtures/platform-pages/generic-company-like.html>

`file://` paths are not supported.

### Real application pages

Greenhouse (`.greenhouse.io`), Lever (`.lever.co`), Ashby (`.ashbyhq.com`), Workday
(`.myworkdayjobs.com`, `.myworkdaysite.com`), and SmartRecruiters
(`.smartrecruiters.com`), over `https` only. Company-hosted forms need an explicit
opt-in via the backend's `PHASE7_APPROVED_DOMAINS` environment variable.

No new permission is requested for any of this. `activeTab` plus `scripting` lets the
popup inject the content script into the tab you are looking at **when you click**, so
nothing runs on a page you did not activate. See
[../docs/platform-support-matrix.md](../docs/platform-support-matrix.md).

## Using it

1. Open the form, then click the extension icon.
2. On a real page: read the warning box and tick the confirmation. The box is unchecked
   every time the popup opens, and the backend refuses the request without it.
3. **Step 1, Scan** - reads field metadata from the page (never values).
4. **Step 2, Build plan** - sends that metadata to the backend and gets a plan
   back. The counts show how many fields are in each group.
5. **Step 3, Review** - the plan is grouped the same way as in the dashboard:
   - **Will fill**: plain profile fields matched with high confidence (0.90+).
   - **Suggested**: probable matches (0.60+). Not filled; type them yourself.
   - **Needs review**: low confidence, no profile value, or a custom control the
     extension cannot set (badged "Not supported").
   - **Protected**: sensitive or legal questions. Never filled.
   - **Skipped**: buttons, hidden, disabled, or read-only fields.

   Click **Why?** on a row to see the evidence behind it. **Highlight on page**
   outlines and badges each field; **Clear highlights** removes that again.
6. **Fill N safe fields** - fills only the fields under Will fill.
7. Read the whole form yourself, then submit it yourself.

A button is disabled until its step can run, and a single line above the steps
says what is in the way (unsupported page, confirmation not ticked, backend not
running, no saved profile, or nothing safe to fill).

## Troubleshooting

### "Cannot reach the local backend at http://127.0.0.1:8000"

The backend is not running, or it is on a different port. Start it with
`uvicorn app.main:app --reload` from `backend/`, and check
<http://127.0.0.1:8000/extension/health> in a normal tab.

### CORS error in the popup console

The backend allows `chrome-extension://<32-char id>` origins via a regex, so this
normally works without configuration. If you see a CORS failure:

- Make sure you restarted uvicorn after pulling the Phase 6 backend changes - the
  CORS rule lives in `backend/app/main.py`.
- Confirm the failing request is going to `127.0.0.1:8000` and not to a different
  host or port.

### "Could not reach the page. Reload the tab..."

The content script is not present in that tab. This happens when the tab was
already open before you loaded or reloaded the extension. Reload the page and try
again.

### The popup says the page is not supported

The page is neither a loopback origin nor a supported platform. Check the reason shown
under the platform name: it will say whether the host was unrecognized, whether the page
was served over `http` instead of `https`, or whether a company domain needs approval.

For a company-hosted form, add the host to `PHASE7_APPROVED_DOMAINS` and restart the
backend:

```powershell
$env:PHASE7_APPROVED_DOMAINS = "careers.acme-corp.example"
uvicorn app.main:app --reload
```

Approval is per host, so `acme-corp.example` does not cover `careers.acme-corp.example`.

### The buttons are disabled on a real page

Tick the confirmation checkbox. Until you do, the buttons stay disabled and the backend
would refuse the request anyway.

### Most Workday fields say "manual review" or "Not supported"

Expected. Workday builds its country, state, and skills pickers from divs, whose value
lives in framework state the DOM does not expose, so writing to them would either do
nothing or corrupt the page. The extension flags them and leaves them to you. Workday is
also a multi-step wizard: only the step on screen is analyzed, and the extension never
presses Next.

### No fields detected

- Confirm the page actually has `<input>`, `<textarea>`, or `<select>` elements.
- Password and hidden inputs are skipped by design and never counted.
- Fields inside an `<iframe>` or a shadow root are not detected. If the popup warns about
  embedded frames, open the form in its own tab.
- On platforms that reveal sections as you scroll (SmartRecruiters especially), scroll to
  the rest of the form and click **Scan again**.

### Values are not filling

Check the warnings list in the popup. The usual causes:

- The field is `manual_review`, `suggest`, or `skip`, so no value was ever sent.
- Your profile has no value for that field (shown as a missing-value reason).
- A `<select>` had no exact option match, so it was left for you to choose.
- The element is disabled or readonly.
- The selector went stale because the page re-rendered - detect and analyze again.

### Sensitive fields are not filled

That is intentional and not a bug. Work authorization, sponsorship, salary,
demographic, disability, veteran, criminal-history, and legal-acknowledgment fields
are always left for you. The backend does not even send a value for them.

### File upload fields are not filled

Also intentional. Browsers do not allow scripts to populate a file input, and
silently attaching a resume should not happen without an explicit choice. Attach
the file yourself.

### The popup shows stale data

The popup keeps its state in memory only, so it resets whenever it closes. If it
looks out of date relative to the page, click **Scan again** and **Rebuild**. After editing your profile in the dashboard,
close and reopen the popup so it re-fetches `/extension/health`.

### Nothing changed after a code edit

Run `npm run build`, click reload on the extension card, then reload the page tab.
Missing any of those three steps leaves old code running.

## Project layout

```
extension/
  popup.html                    popup entry (Vite input; emits dist/popup.html)
  vite.config.ts                popup build
  vitest.config.ts              test config (jsdom)
  scripts/build-scripts.mjs     esbuild IIFE build for content + worker
  public/manifest.json          MV3 manifest (copied to dist/)
  src/
    background/serviceWorker.ts minimal: seeds the backend URL setting
    content/
      contentScript.ts          message handler; acts only when asked
      fieldDetector.ts          metadata-only field detection
      pageHighlighter.ts        outlines and badges per decision
      platformDetector.ts       URL identity + DOM shape -> which adapter
      safeFiller.ts             final safety gate before touching the DOM
      adapters/
        index.ts                registry and adapter selection
        adapterUtils.ts         shared label/signal helpers
        genericAdapter.ts       plain-HTML fallback
        greenhouseAdapter.ts    per-platform metadata only
        leverAdapter.ts
        ashbyAdapter.ts
        workdayAdapter.ts
        smartRecruitersAdapter.ts
    popup/
      Popup.tsx                 UI and orchestration
      main.tsx                  React entry
      popup.css                 styles
      components/
        PlatformStatus.tsx      what the backend says about this page
        RealPageWarning.tsx     the confirmation gate
        FillPlanReview.tsx      grouped, redacted plan
    shared/
      apiClient.ts              local backend client
      constants.ts              origins, actions, message names
      permissions.ts            documents and checks the permission model
      platformTypes.ts          mirrors backend/app/models/platform.py
      types.ts                  mirrors backend/app/models/extension.py
      urlSafety.ts              client-side mirror of the backend URL rules
```

`urlSafety.ts` mirrors the backend allow-list so the popup can decide what to show
without a round trip. It is presentation only - the backend re-checks every URL, and it
is the backend's answer that governs.

## Permissions, and why each is needed

| Permission | Why |
| --- | --- |
| `activeTab` | temporary access to the tab you clicked the extension on, expiring on navigation |
| `scripting` | inject the content script into that tab on demand - how real pages are handled |
| `storage` | remember the backend URL (never profile data) |
| six loopback `host_permissions` | reach the local backend, the sample forms, and the fixtures |

Deliberately **not** requested: `<all_urls>`, any job-board or ATS domain,
`optional_host_permissions`, `tabs`, `history`, `bookmarks`, `webNavigation`, or
`cookies`.

Real-page support needs no additional permission because `activeTab` already grants
exactly the access the design calls for: one tab, only after you interact with the
extension, gone on navigation. A standing host permission for the ATS domains would be
strictly worse, since it would let the extension act on those sites without you asking.

`src/shared/permissions.spec.ts` asserts this against `public/manifest.json`, so adding a
broad host permission or a declarative content script beyond the loopback origins fails
the test suite.
