/**
 * Adapter for SmartRecruiters-hosted application forms (Phase 7).
 *
 * SmartRecruiters exposes `data-test` attributes on most controls, which the
 * detector already prefers for selectors, so they are also the best label fallback
 * here. Two platform quirks are worth naming:
 *
 * - Location is an autocomplete widget rather than a text input, so it is flagged as
 *   a custom control and left alone.
 * - Sections of the form are revealed as the user scrolls or expands them, so a
 *   detection run only ever sees what is currently rendered.
 */

import type { ExtensionDetectedField } from "../../shared/types";
import type { PlatformAdapter } from "../../shared/platformTypes";
import {
  enhanceWithAttributeLabels,
  iframeWarning,
  matchedSelectors,
} from "./adapterUtils";
import { applyGenericEnhancements } from "./genericAdapter";

const SIGNALS = [
  "#st-application",
  "form[data-test='application-form']",
  "[data-test='application-page']",
  "[data-test='resume-upload']",
] as const;

const LABEL_ATTRIBUTES = ["data-test", "name", "id"] as const;

export const smartRecruitersAdapter: PlatformAdapter = {
  platformId: "smartrecruiters",
  displayName: "SmartRecruiters",

  detectPlatformSignals(doc: Document) {
    const matched = matchedSelectors(doc, SIGNALS);
    return { matched, confidence: matched.length ? 0.9 : 0 };
  },

  enhanceDetectedFields(fields: ExtensionDetectedField[], doc: Document) {
    const generic = applyGenericEnhancements(fields, doc);
    return enhanceWithAttributeLabels(generic, doc, LABEL_ATTRIBUTES).map((field) => {
      if (!field.is_custom_control || field.unsupported_reason) return field;
      return {
        ...field,
        unsupported_reason:
          "SmartRecruiters autocomplete widget; choose a value yourself",
      };
    });
  },

  getUnsupportedWarnings(doc: Document) {
    return [
      "SmartRecruiters reveals form sections as you scroll. Only the fields currently " +
        "rendered were analyzed; run Detect fields again after the rest appears.",
      ...iframeWarning(doc, "SmartRecruiters"),
    ];
  },
};
