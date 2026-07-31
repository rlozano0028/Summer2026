/**
 * Adapter for Lever-hosted application forms (Phase 7).
 *
 * Lever uses native inputs with `data-qa` attributes and two naming conventions
 * that carry real meaning:
 *
 * - `urls[LinkedIn]`, `urls[GitHub]`, `urls[Portfolio]` - the link type is in the
 *   name, so a field with no label can still be identified confidently.
 * - `cards[<section>][fieldN]` - custom question sections, where the index says
 *   nothing. Those fall back to the wrapper text the detector already captured.
 */

import type { ExtensionDetectedField } from "../../shared/types";
import type { PlatformAdapter } from "../../shared/platformTypes";
import { humanizeToken, iframeWarning, matchedSelectors } from "./adapterUtils";
import { applyGenericEnhancements } from "./genericAdapter";

const SIGNALS = [
  "form[data-qa='application-form']",
  "[data-qa='resume-upload-input']",
  ".application-form",
  "input[name^='urls[']",
  "input[name^='cards[']",
] as const;

/** Extract `LinkedIn` from `urls[LinkedIn]`, or null when the name is not a URL slot. */
function urlSlotLabel(name: string | null): string | null {
  const match = /^urls\[(.+)\]$/.exec(name ?? "");
  if (!match) return null;
  const readable = humanizeToken(match[1]);
  return readable ? `${readable} url` : null;
}

export const leverAdapter: PlatformAdapter = {
  platformId: "lever",
  displayName: "Lever",

  detectPlatformSignals(doc: Document) {
    const matched = matchedSelectors(doc, SIGNALS);
    return { matched, confidence: matched.length ? 0.9 : 0 };
  },

  enhanceDetectedFields(fields: ExtensionDetectedField[], doc: Document) {
    return applyGenericEnhancements(fields, doc).map((field) => {
      if (field.label_text || field.aria_label) return field;
      const fromUrlSlot = urlSlotLabel(field.name);
      if (fromUrlSlot) return { ...field, label_text: fromUrlSlot };
      if ((field.name ?? "").startsWith("cards[") && field.nearby_text) {
        return { ...field, label_text: field.nearby_text };
      }
      return field;
    });
  },

  getUnsupportedWarnings(doc: Document) {
    return iframeWarning(doc, "Lever");
  },
};
