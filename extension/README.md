# Autofill Assistant - Chrome extension (Phase 6 prototype)

A Manifest V3 extension that asks the local FastAPI backend how to fill the form on
the current page, shows you the plan, and fills only the fields you approve.

**Local sample forms only. Nothing is ever submitted.** See
[../docs/phase-6-chrome-extension-integration.md](../docs/phase-6-chrome-extension-integration.md)
for the full design and privacy model.

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
| `npm run clean` | delete `dist/` |

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

The manifest grants host permissions for these six origins only, and the backend
enforces the same list:

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

`file://` paths are not supported.

## Using it

1. Open a sample form, then click the extension icon.
2. **Detect fields** - reads field metadata from the page (never values).
3. **Analyze with local profile** - sends that metadata to the backend and gets a
   plan back.
4. **Highlight decisions** - outlines and badges each field on the page.
5. **Apply safe fills** - fills only the `fill` decisions.
6. **Clear highlights** - removes the page decoration.

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

You are on an origin outside the six allow-listed ones - a `file://` path or a real
website. Phase 6 is deliberately limited to local development pages.

### No fields detected

- Confirm the page actually has `<input>`, `<textarea>`, or `<select>` elements.
- Password inputs are skipped by design and never counted.
- Fields inside an `<iframe>` or a shadow root are not detected in Phase 6.

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
looks out of date relative to the page, click **Detect fields** and
**Analyze with local profile** again. After editing your profile in the dashboard,
close and reopen the popup so it re-fetches `/extension/health`.

### Nothing changed after a code edit

Run `npm run build`, click reload on the extension card, then reload the page tab.
Missing any of those three steps leaves old code running.

## Project layout

```
extension/
  popup.html                    popup entry (Vite input; emits dist/popup.html)
  vite.config.ts                popup build
  scripts/build-scripts.mjs     esbuild IIFE build for content + worker
  public/manifest.json          MV3 manifest (copied to dist/)
  src/
    background/serviceWorker.ts minimal: seeds the backend URL setting
    content/
      contentScript.ts          message handler; acts only when asked
      fieldDetector.ts          metadata-only field detection
      pageHighlighter.ts        outlines and badges per decision
      safeFiller.ts             final safety gate before touching the DOM
    popup/
      Popup.tsx                 UI and orchestration
      main.tsx                  React entry
      popup.css                 styles
    shared/
      apiClient.ts              local backend client + isAllowedPageUrl
      constants.ts              origins, actions, message names
      types.ts                  mirrors backend/app/models/extension.py
```

## Permissions, and why each is needed

| Permission | Why |
| --- | --- |
| `activeTab` | act on the tab you clicked the extension on |
| `scripting` | reserved for re-injecting the content script into tabs opened before install |
| `storage` | remember the backend URL (never profile data) |
| six loopback `host_permissions` | reach the local backend and the local sample forms |

Deliberately **not** requested: `<all_urls>`, any job-board domain, `tabs`,
`history`, `bookmarks`, or `cookies`.
