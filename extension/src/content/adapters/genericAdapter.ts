/**
 * Adapter for standard HTML application forms (Phase 7).
 *
 * The fallback used for any page without ATS-specific markers, and the baseline the
 * other adapters build on. It assumes nothing beyond ordinary HTML: real `<label>`
 * elements, `name` attributes, and `autocomplete` hints.
 *
 * Its only enhancement is to derive a label from common test-id attributes when a
 * field has no label at all, which is the usual failure mode on hand-rolled forms.
 */

import type { ExtensionDetectedField } from "../../shared/types";
import type { PlatformAdapter } from "../../shared/platformTypes";
import {
  enhanceWithAttributeLabels,
  iframeWarning,
  matchedSelectors,
} from "./adapterUtils";

/** Signals that a page is an application form rather than, say, a job listing. */
const FORM_SIGNALS = [
  "form input[type='email']",
  "form input[type='file']",
  "input[name*='resume' i]",
  "input[id*='resume' i]",
  "form textarea",
] as const;

const LABEL_ATTRIBUTES = ["data-testid", "data-test", "name", "id"] as const;

export const genericAdapter: PlatformAdapter = {
  platformId: "generic",
  displayName: "Company-hosted form",

  detectPlatformSignals(doc: Document) {
    const matched = matchedSelectors(doc, FORM_SIGNALS);
    // Never high confidence: "it has a form" is weak evidence, and claiming
    // otherwise would make the popup sound more certain than it is.
    const confidence = matched.length >= 2 ? 0.5 : matched.length === 1 ? 0.3 : 0.1;
    return { matched, confidence };
  },

  enhanceDetectedFields(fields: ExtensionDetectedField[], doc: Document) {
    return enhanceWithAttributeLabels(fields, doc, LABEL_ATTRIBUTES);
  },

  getUnsupportedWarnings(doc: Document) {
    return iframeWarning(doc, "company");
  },
};

/** Exported so other adapters can reuse the generic pass before their own. */
export function applyGenericEnhancements(
  fields: ExtensionDetectedField[],
  doc: Document,
): ExtensionDetectedField[] {
  return genericAdapter.enhanceDetectedFields(fields, doc);
}
