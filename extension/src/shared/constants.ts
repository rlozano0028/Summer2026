/**
 * Shared constants for the Phase 6 extension.
 *
 * Kept in one place so the popup, content script, and service worker cannot
 * drift apart on origins, action names, or message names.
 */

/** Local FastAPI backend. Phase 6 never talks to anything else. */
export const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

/**
 * Loopback origins the extension is allowed to operate on. This mirrors
 * ALLOWED_PAGE_ORIGINS in backend/app/models/extension.py; the backend enforces
 * the same list, so a mismatch here fails safe (the request is rejected).
 */
export const ALLOWED_PAGE_ORIGINS = [
  "http://127.0.0.1:8000",
  "http://localhost:8000",
  "http://127.0.0.1:5173",
  "http://localhost:5173",
  "http://127.0.0.1:8080",
  "http://localhost:8080",
] as const;

/** Mapping decision actions, matching the backend's ALLOWED_ACTIONS. */
export const ACTION_FILL = "fill";
export const ACTION_SUGGEST = "suggest";
export const ACTION_MANUAL_REVIEW = "manual_review";
export const ACTION_SKIP = "skip";

export const ACTIONS = [
  ACTION_FILL,
  ACTION_SUGGEST,
  ACTION_MANUAL_REVIEW,
  ACTION_SKIP,
] as const;

/** Human-readable labels for the popup and page badges. */
export const ACTION_LABELS: Record<string, string> = {
  [ACTION_FILL]: "Fill",
  [ACTION_SUGGEST]: "Suggest",
  [ACTION_MANUAL_REVIEW]: "Manual review",
  [ACTION_SKIP]: "Skip",
};

/** Messages the popup sends to the content script. */
export const MSG_DETECT_FIELDS = "DETECT_FIELDS";
export const MSG_APPLY_FILL_INSTRUCTIONS = "APPLY_FILL_INSTRUCTIONS";
export const MSG_HIGHLIGHT_FIELDS = "HIGHLIGHT_FIELDS";
export const MSG_CLEAR_HIGHLIGHTS = "CLEAR_HIGHLIGHTS";
export const MSG_PING = "PING";

/** chrome.storage.local key holding the backend URL setting. Never profile data. */
export const STORAGE_KEY_BACKEND_URL = "backendUrl";

/** Input types the extension refuses to fill, whatever the plan says. */
export const NEVER_FILL_INPUT_TYPES = new Set([
  "password",
  "file",
  "submit",
  "button",
  "reset",
  "image",
  "hidden",
]);
