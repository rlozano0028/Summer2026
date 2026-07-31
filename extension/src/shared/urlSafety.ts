/**
 * URL rules, mirroring backend/app/services/platform_allowlist.py.
 *
 * This is a UX layer, not the security boundary: the backend re-derives the
 * platform and re-checks the allow-list on every request, and it is the only thing
 * that can authorize an analysis. The point of duplicating the rules here is to
 * avoid showing the user an "Analyze" button that is guaranteed to fail, and to
 * avoid injecting a content script into a page we already know is out of scope.
 *
 * Every function fails closed. An unparseable URL, a missing URL, or a
 * `chrome://` / `file://` / `about:` URL is treated as unsupported.
 */

import { ALLOWED_PAGE_ORIGINS, PLATFORM_HOST_SUFFIXES } from "./constants";
import type { PlatformId } from "./platformTypes";

/** Return the lowercased hostname, or "" when the URL cannot be parsed. */
export function getDomain(url: string | undefined | null): string {
  if (!url) return "";
  try {
    return new URL(url).hostname.toLowerCase().replace(/\.$/, "");
  } catch {
    return "";
  }
}

/** True for the loopback origins Phase 6 supports. Compares the whole origin. */
export function isLocalUrl(url: string | undefined | null): boolean {
  if (!url) return false;
  try {
    return (ALLOWED_PAGE_ORIGINS as readonly string[]).includes(new URL(url).origin);
  } catch {
    return false;
  }
}

/**
 * Match a host against one pattern on label boundaries.
 *
 * `.lever.co` matches `lever.co` and `jobs.lever.co` but not `notlever.co` or
 * `lever.co.evil.example`.
 */
function hostMatches(host: string, pattern: string): boolean {
  if (!host || !pattern) return false;
  const lowered = pattern.toLowerCase();
  if (lowered.startsWith(".")) {
    return host === lowered.slice(1) || host.endsWith(lowered);
  }
  return host === lowered;
}

/**
 * Identify a supported ATS from the URL alone, or null.
 *
 * Real platforms must be https. Anything else - including a company-hosted form the
 * backend may have approved - returns null here, because the extension cannot know
 * the backend's `PHASE7_APPROVED_DOMAINS` value without asking it.
 */
export function getKnownPlatformForUrl(
  url: string | undefined | null,
): PlatformId | null {
  if (!url) return null;
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (parsed.protocol !== "https:") return null;
  const host = parsed.hostname.toLowerCase().replace(/\.$/, "");
  for (const [platformId, patterns] of Object.entries(PLATFORM_HOST_SUFFIXES)) {
    if (patterns.some((pattern) => hostMatches(host, pattern))) {
      return platformId as PlatformId;
    }
  }
  return null;
}

/** True when the URL is a supported ATS host over https. */
export function isKnownSupportedPlatformUrl(url: string | undefined | null): boolean {
  return getKnownPlatformForUrl(url) !== null;
}

/**
 * True when a URL is one the extension may even consider.
 *
 * Browser-internal pages (`chrome://`, `chrome-extension://`, `about:`,
 * `view-source:`) and `file://` pages are excluded: a content script either cannot
 * run there or should not.
 */
export function isInjectableUrl(url: string | undefined | null): boolean {
  if (!url) return false;
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  return parsed.protocol === "http:" || parsed.protocol === "https:";
}

/**
 * Rough guess at whether a page is an application form, from its URL only.
 *
 * Used to soften the popup's copy on a company domain ("this looks like an
 * application page") - never to grant access. A false positive changes nothing,
 * because the backend still has to approve the domain.
 */
export function isProbablyApplicationPage(url: string | undefined | null): boolean {
  if (!url) return false;
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  const haystack = `${parsed.pathname}${parsed.search}`.toLowerCase();
  return [
    "apply",
    "application",
    "careers",
    "career",
    "jobs",
    "job",
    "opening",
    "position",
    "vacancy",
    "recruit",
  ].some((needle) => haystack.includes(needle));
}

/**
 * True when the user must explicitly confirm before this page is analyzed.
 *
 * Loopback pages never require confirmation (Phase 6 behaviour is preserved
 * exactly). Everything else does, including pages the extension does not
 * recognize: requiring confirmation on an unknown page is harmless, since the
 * backend will refuse it anyway, whereas *not* requiring it would be a bug.
 */
export function shouldRequireRealPageConfirmation(
  url: string | undefined | null,
): boolean {
  return !isLocalUrl(url);
}
