/**
 * Adapter for Ashby-hosted application forms (Phase 7).
 *
 * Ashby renders a React form with hashed CSS class names, so class names are
 * useless as evidence and are not used. Two things matter here:
 *
 * - System fields are named `_systemfield_email` and similar. Stripping the prefix
 *   gives a usable label when the visible one is missing.
 * - Long answers are often contenteditable rich-text boxes and some pickers are
 *   listbox widgets. The detector flags those as custom controls; this adapter adds
 *   the explanation the user sees, and the extension never writes to them.
 *
 * Ashby's native inputs are React-controlled, which the shared filler already
 * handles by going through the prototype value setter and dispatching events.
 */

import type { ExtensionDetectedField } from "../../shared/types";
import type { PlatformAdapter } from "../../shared/platformTypes";
import { humanizeToken, matchedSelectors } from "./adapterUtils";
import { applyGenericEnhancements } from "./genericAdapter";

const SIGNALS = [
  "#ashby-application-form-container",
  "[data-highlight='ashby']",
  "input[name^='_systemfield_']",
  "[id^='_systemfield_']",
] as const;

const SYSTEM_FIELD_PREFIX = "_systemfield_";

export const ashbyAdapter: PlatformAdapter = {
  platformId: "ashby",
  displayName: "Ashby",

  detectPlatformSignals(doc: Document) {
    const matched = matchedSelectors(doc, SIGNALS);
    return { matched, confidence: matched.length ? 0.9 : 0 };
  },

  enhanceDetectedFields(fields: ExtensionDetectedField[], doc: Document) {
    return applyGenericEnhancements(fields, doc).map((field) => {
      const enhanced = { ...field };

      if (!enhanced.label_text && !enhanced.aria_label) {
        const source = enhanced.name ?? enhanced.id_attribute ?? "";
        if (source.startsWith(SYSTEM_FIELD_PREFIX)) {
          const readable = humanizeToken(source.slice(SYSTEM_FIELD_PREFIX.length));
          if (readable) enhanced.label_text = readable;
        }
      }

      if (enhanced.is_custom_control && !enhanced.unsupported_reason) {
        enhanced.unsupported_reason =
          "Ashby rich-text or picker control; type into it yourself";
      }
      return enhanced;
    });
  },

  getUnsupportedWarnings() {
    return [
      "Ashby answer boxes are often rich-text editors rather than plain text areas. " +
        "Those are left for you to fill.",
    ];
  },
};
