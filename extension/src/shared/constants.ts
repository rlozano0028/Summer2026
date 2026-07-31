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
/** Phase 7: ask the content script which platform the page looks like. */
export const MSG_DETECT_PLATFORM = "DETECT_PLATFORM";

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

/**
 * Phase 7: host suffixes for the supported applicant tracking systems.
 *
 * Mirrors the rules in backend/app/services/platform_allowlist.py. A leading dot
 * means "this host or any subdomain". The backend re-derives the platform from the
 * URL on every request, so a mismatch here fails safe: the popup may look wrong,
 * but the analysis is still refused.
 */
export const PLATFORM_HOST_SUFFIXES: Record<string, readonly string[]> = {
  greenhouse: [".greenhouse.io"],
  lever: [".lever.co"],
  ashby: [".ashbyhq.com"],
  workday: [".myworkdayjobs.com", ".myworkdaysite.com"],
  smartrecruiters: [".smartrecruiters.com"],
};

/** Display names for the platform ids above, plus the two special cases. */
export const PLATFORM_LABELS: Record<string, string> = {
  local: "Local sample form",
  generic: "Company-hosted form",
  greenhouse: "Greenhouse",
  lever: "Lever",
  ashby: "Ashby",
  workday: "Workday",
  smartrecruiters: "SmartRecruiters",
  unsupported: "Unsupported page",
};

/** Backend paths used by Phase 7. Listed here so the client cannot typo them. */
export const PATH_ANALYZE_REAL_PAGE = "/extension/analyze-real-page";
export const PATH_SUPPORTED_PLATFORMS = "/platforms/supported";
export const PATH_CHECK_URL = "/platforms/check-url";
