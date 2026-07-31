/**
 * Adapter for Greenhouse-hosted application forms (Phase 7).
 *
 * Greenhouse is the friendliest of the supported platforms: mostly native inputs
 * with real `<label for=...>` elements, so the generic pass already handles it. Two
 * things are worth adding:
 *
 * - Custom questions are named `job_application[answers_attributes][N][text_value]`,
 *   which says nothing about the question. The visible question text lives in a
 *   sibling label, so when a field has no label we fall back to its wrapper text.
 * - Company career sites frequently embed the Greenhouse form in an iframe. A
 *   content script cannot see into it, and we will not try, so the user is told.
 */

import type { ExtensionDetectedField } from "../../shared/types";
import type { PlatformAdapter } from "../../shared/platformTypes";
import { iframeWarning, matchedSelectors } from "./adapterUtils";
import { applyGenericEnhancements } from "./genericAdapter";

const SIGNALS = [
  "#application_form",
  "#grnhse_app",
  "form.application--form",
  "[id^='job_application_answers']",
  "input[name^='job_application']",
  "iframe[src*='greenhouse.io']",
] as const;

/**
 * Greenhouse answer inputs whose name is an index rather than a question.
 * Matching on the name prefix keeps this narrow.
 */
function isOpaqueAnswerField(field: ExtensionDetectedField): boolean {
  return (field.name ?? "").startsWith("job_application[answers_attributes]");
}

export const greenhouseAdapter: PlatformAdapter = {
  platformId: "greenhouse",
  displayName: "Greenhouse",

  detectPlatformSignals(doc: Document) {
    const matched = matchedSelectors(doc, SIGNALS);
    return { matched, confidence: matched.length ? 0.9 : 0 };
  },

  enhanceDetectedFields(fields: ExtensionDetectedField[], doc: Document) {
    return applyGenericEnhancements(fields, doc).map((field) => {
      if (field.label_text || field.aria_label || !isOpaqueAnswerField(field)) {
        return field;
      }
      // nearby_text is already collected and length-capped by the detector; reusing
      // it here avoids reading any additional page text.
      return field.nearby_text ? { ...field, label_text: field.nearby_text } : field;
    });
  },

  getUnsupportedWarnings(doc: Document) {
    return iframeWarning(doc, "Greenhouse");
  },
};
