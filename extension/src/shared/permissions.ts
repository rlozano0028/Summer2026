/**
 * How Phase 7 reaches a real page, and why it needs no new permissions.
 *
 * The manifest declares `activeTab` and `scripting`, and a declarative content
 * script only for the six loopback origins. That combination is deliberate:
 *
 * - `activeTab` grants temporary access to the tab the user is looking at, and only
 *   after they interact with the extension. It expires on navigation. There is no
 *   `<all_urls>` host permission and no permission prompt.
 * - `scripting` lets the popup inject the content script into that tab on demand,
 *   which is how real pages are handled. Nothing runs on a page the user did not
 *   activate by clicking a button in the popup.
 *
 * So Phase 7 needs no `optional_host_permissions` and requests nothing at runtime.
 * The functions here exist to make that reasoning checkable in code rather than
 * only in a comment, and to give the popup a single place to explain it.
 */

import { isInjectableUrl } from "./urlSafety";

/**
 * True when the extension can act on this tab without asking for a permission.
 *
 * `activeTab` covers any http(s) page the user has focused, so the only real
 * constraint is that a content script can run there at all.
 */
export function canAccessTabOnUserAction(url: string | undefined | null): boolean {
  return isInjectableUrl(url);
}

/**
 * Human-readable reason a tab cannot be used, or null when it can.
 *
 * Kept as copy rather than an error code because it is shown directly in the popup.
 */
export function describeTabAccessProblem(
  url: string | undefined | null,
): string | null {
  if (!url) {
    return "No active tab was found. Focus the tab with the application form.";
  }
  if (!isInjectableUrl(url)) {
    return (
      "This extension can only run on http(s) pages. Browser pages, extension " +
      "pages, and local files are out of scope."
    );
  }
  return null;
}

/**
 * The permissions Phase 7 relies on. Asserted in tests against the manifest so
 * that adding a broad host permission later cannot pass unnoticed.
 */
export const REQUIRED_PERMISSIONS = ["activeTab", "scripting", "storage"] as const;

/** Host permissions that would be a red flag if they ever appeared. */
export const FORBIDDEN_HOST_PERMISSIONS = [
  "<all_urls>",
  "*://*/*",
  "http://*/*",
  "https://*/*",
] as const;
