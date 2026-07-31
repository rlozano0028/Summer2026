/**
 * Minimal MV3 service worker (Phase 6).
 *
 * Intentionally does almost nothing. It exists so the extension has a valid
 * background entry point and so the default backend URL setting is seeded on
 * install. It deliberately does NOT:
 * - autofill anything,
 * - scan or read pages,
 * - talk to the backend,
 * - collect browsing data,
 * - keep any state about pages the user visits.
 *
 * All work happens in the popup (network) and the content script (DOM), and only
 * after the user clicks a button.
 */

import { DEFAULT_BACKEND_URL, STORAGE_KEY_BACKEND_URL } from "../shared/constants";

chrome.runtime.onInstalled.addListener(async () => {
  // Seed the one setting we store. No profile data is ever kept in storage.
  const stored = await chrome.storage.local.get(STORAGE_KEY_BACKEND_URL);
  if (!stored[STORAGE_KEY_BACKEND_URL]) {
    await chrome.storage.local.set({ [STORAGE_KEY_BACKEND_URL]: DEFAULT_BACKEND_URL });
  }
});
