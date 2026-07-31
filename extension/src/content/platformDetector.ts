/**
 * Work out what kind of page the content script is running on (Phase 7).
 *
 * Detection combines two independent sources:
 *
 * - The URL, which is authoritative for *identity* (only a `.lever.co` page is
 *   Lever) and is the same rule the backend enforces.
 * - DOM signals, which are authoritative for *shape* (which adapter can read this
 *   page best).
 *
 * They can disagree, and that is fine. A Greenhouse-shaped fixture served from
 * `127.0.0.1` is reported as `local` - because that is what it is, and what the
 * safety layer must see - while the Greenhouse adapter is still used to read it. The
 * disagreement is recorded in `matched_by` rather than resolved silently.
 *
 * Nothing here decides whether a page may be analyzed. That answer comes from the
 * backend, which re-derives it from the URL on every request.
 */

import { PLATFORM_LABELS } from "../shared/constants";
import type {
  DetectPlatformResult,
  PageSignals,
  PlatformAdapter,
  PlatformId,
} from "../shared/platformTypes";
import { getKnownPlatformForUrl, isLocalUrl } from "../shared/urlSafety";
import { getAdapterById, selectAdapter } from "./adapters";

/**
 * Collect non-identifying structural facts about the page.
 *
 * Counts and booleans only: no text, no values, no attribute contents. This is what
 * gets shown in the popup and, deliberately, is safe to show.
 */
export function getPageSignals(doc: Document = document): PageSignals {
  const inputs = Array.from(doc.querySelectorAll("input, textarea, select"));
  const location = doc.defaultView?.location;
  return {
    hostname: (location?.hostname ?? "").toLowerCase(),
    pathname: location?.pathname ?? "",
    formCount: doc.querySelectorAll("form").length,
    inputCount: inputs.length,
    fileInputCount: doc.querySelectorAll("input[type='file']").length,
    iframeCount: doc.querySelectorAll("iframe").length,
    hasPasswordField: doc.querySelector("input[type='password']") !== null,
    matchedSelectors: [],
    looksLikeApplicationForm: false,
  };
}

/**
 * True when the page looks like something a person fills in and submits.
 *
 * Used only to soften copy in the popup. A job *listing* has links and no inputs; an
 * application form has several inputs and usually a file upload or a textarea.
 */
function looksLikeApplicationForm(signals: PageSignals, doc: Document): boolean {
  if (signals.inputCount < 3) return false;
  if (signals.fileInputCount > 0) return true;
  return doc.querySelector("textarea, input[type='email']") !== null;
}

/**
 * Identify the current page and the adapter to read it with.
 *
 * `platform_id` follows the URL, because that is what the safety layer keys on.
 * `matched_by` records both sources so a surprising result is explainable.
 */
export function detectCurrentPlatform(doc: Document = document): DetectPlatformResult {
  const pageUrl = doc.defaultView?.location?.href ?? "";
  const signals = getPageSignals(doc);

  const { adapter, matched, confidence } = selectAdapter(doc);
  signals.matchedSelectors = matched;
  signals.looksLikeApplicationForm = looksLikeApplicationForm(signals, doc);

  const urlPlatform: PlatformId | null = isLocalUrl(pageUrl)
    ? "local"
    : getKnownPlatformForUrl(pageUrl);

  const matchedBy = [
    ...matched.map((selector) => `page-signal:${selector}`),
    ...(urlPlatform ? [`url:${urlPlatform}`] : []),
  ];

  const warnings = adapter.getUnsupportedWarnings(doc);
  if (signals.hasPasswordField) {
    warnings.push(
      "This page has a password field. It is ignored entirely - the extension never " +
        "reads or fills passwords.",
    );
  }
  if (urlPlatform && urlPlatform !== "local" && adapter.platformId !== urlPlatform) {
    warnings.push(
      `The page URL says ${PLATFORM_LABELS[urlPlatform] ?? urlPlatform} but its markup ` +
        `looks like ${adapter.displayName}. Field detection may be less accurate.`,
    );
  }

  // The URL wins for identity. On a local page that means "local", even when the
  // DOM looks exactly like a vendor form.
  const platformId: PlatformId = urlPlatform ?? "unsupported";

  return {
    platform_id: platformId,
    display_name: PLATFORM_LABELS[platformId] ?? adapter.displayName,
    // Confidence describes the adapter match, which is what varies; the URL match is
    // binary and already reflected in platform_id.
    confidence: Number(confidence.toFixed(2)),
    matched_by: matchedBy,
    page_url: pageUrl,
    signals,
    warnings,
  };
}

/**
 * The adapter to use for reading fields on this page.
 *
 * Signal-driven, so a local fixture that imitates a vendor form is read by that
 * vendor's adapter. Falls back to the generic adapter.
 */
export function getActiveAdapter(doc: Document = document): PlatformAdapter {
  return selectAdapter(doc).adapter;
}

export { getAdapterById };
