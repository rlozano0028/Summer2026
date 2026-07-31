/**
 * Adapter for Workday-hosted application forms (Phase 7).
 *
 * Workday is the hardest platform supported here, and this adapter is written to be
 * conservative rather than clever:
 *
 * - `data-automation-id` is the one reliable identifier on the page, and it is often
 *   the *only* one, so it is the primary label source.
 * - Country, state, and skills are button-driven listboxes, not `<select>`s. The
 *   detector flags them as custom controls and they route to manual review.
 * - The form is a multi-step wizard. The extension only ever looks at the step
 *   currently on screen and never advances it: no clicking Next, no clicking Save
 *   and Continue, no navigation of any kind.
 *
 * Because so much of a Workday form is out of scope, the warnings here are blunt.
 * Overstating what this can do on Workday would be the actual failure.
 */

import type { ExtensionDetectedField } from "../../shared/types";
import type { PlatformAdapter } from "../../shared/platformTypes";
import { enhanceWithAttributeLabels, matchedSelectors } from "./adapterUtils";
import { applyGenericEnhancements } from "./genericAdapter";

const SIGNALS = [
  "[data-automation-id='applyFlowPage']",
  "[data-automation-id='applicationForm']",
  "[data-automation-id^='legalNameSection']",
  "[data-automation-id]",
] as const;

const LABEL_ATTRIBUTES = ["data-automation-id", "name", "id"] as const;

/** Wizard navigation controls. Named so the popup can say we ignore them. */
const NAVIGATION_SELECTORS = [
  "[data-automation-id='bottom-navigation-next-button']",
  "[data-automation-id='bottom-navigation-back-button']",
] as const;

export const workdayAdapter: PlatformAdapter = {
  platformId: "workday",
  displayName: "Workday",

  detectPlatformSignals(doc: Document) {
    const matched = matchedSelectors(doc, SIGNALS);
    // The bare [data-automation-id] selector alone is weaker evidence than the
    // named containers, so a lone match gets a lower score.
    const confidence = matched.length > 1 ? 0.9 : matched.length === 1 ? 0.7 : 0;
    return { matched, confidence };
  },

  enhanceDetectedFields(fields: ExtensionDetectedField[], doc: Document) {
    const generic = applyGenericEnhancements(fields, doc);
    return enhanceWithAttributeLabels(generic, doc, LABEL_ATTRIBUTES).map((field) => {
      if (!field.is_custom_control || field.unsupported_reason) return field;
      return {
        ...field,
        unsupported_reason:
          "Workday dropdown widget; open it and choose an option yourself",
      };
    });
  },

  getUnsupportedWarnings(doc: Document) {
    const warnings = [
      "Workday forms are multi-step. Only the step currently on screen is analyzed, " +
        "and the extension never presses Next, Back, or Save and Continue.",
      "Workday country, state, and skills pickers are custom widgets. They are always " +
        "left for you.",
    ];
    if (matchedSelectors(doc, NAVIGATION_SELECTORS).length > 0) {
      warnings.push(
        "This step has navigation buttons. Move between steps yourself, then run " +
          "Detect fields again on the new step.",
      );
    }
    return warnings;
  },
};
