/**
 * Helpers shared by the platform adapters.
 *
 * Adapters do one thing: make field metadata more informative so the Phase 5
 * engine has something to match on. On a hand-written form the `<label>` is
 * usually enough; on a real ATS the visible label is often a `<span>` two levels
 * up while the useful identifier hides in a `data-automation-id` or `data-qa`
 * attribute. These helpers turn those attributes into label-like text.
 *
 * Nothing here reads element values, clicks, or navigates.
 */

import type { ExtensionDetectedField } from "../../shared/types";

/** Cap on derived text, matching the detector's nearby-text limit. */
const DERIVED_TEXT_LIMIT = 160;

/** Which of `selectors` are present in `doc`. Invalid selectors are ignored. */
export function matchedSelectors(
  doc: Document,
  selectors: readonly string[],
): string[] {
  const matched: string[] = [];
  for (const selector of selectors) {
    try {
      if (doc.querySelector(selector)) matched.push(selector);
    } catch {
      // A malformed selector is a bug in the adapter, not a page problem.
    }
  }
  return matched;
}

/**
 * Turn an attribute token into readable words.
 *
 * `legalNameSection_firstName` becomes `legal name section first name`, which is
 * the form the mapping engine's text matching expects. Returns "" when the token
 * carries no letters (a hash, an id, a GUID), because inventing a label from noise
 * would be worse than having none.
 */
export function humanizeToken(token: string | null | undefined): string {
  if (!token) return "";
  const spaced = token
    .replace(/[_\-.[\]]+/g, " ")
    .replace(/([a-z\d])([A-Z])/g, "$1 $2")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
  // Reject strings that are mostly digits/hex noise rather than words.
  const letters = spaced.replace(/[^a-z]/g, "");
  if (letters.length < 3) return "";
  return spaced.slice(0, DERIVED_TEXT_LIMIT);
}

/** Resolve the element a detected field refers to, or null. */
export function resolveField(
  doc: Document,
  field: ExtensionDetectedField,
): Element | null {
  try {
    return doc.querySelector(field.selector);
  } catch {
    return null;
  }
}

/**
 * Fill in `label_text` from the first attribute in `attributeNames` that yields
 * readable words, when the field has no label of its own.
 *
 * Existing labels are never overwritten: the page's own wording is always better
 * evidence than a developer's attribute name.
 */
export function deriveLabelFromAttributes(
  field: ExtensionDetectedField,
  el: Element | null,
  attributeNames: readonly string[],
): ExtensionDetectedField {
  if (field.label_text || field.aria_label || !el) return field;
  for (const attribute of attributeNames) {
    const derived = humanizeToken(el.getAttribute(attribute));
    if (derived) {
      return { ...field, label_text: derived };
    }
  }
  return field;
}

/**
 * Apply `deriveLabelFromAttributes` to every field in one pass.
 *
 * Adapters call this instead of writing their own loop, so they stay short enough
 * to read as "here is what this platform names things".
 */
export function enhanceWithAttributeLabels(
  fields: ExtensionDetectedField[],
  doc: Document,
  attributeNames: readonly string[],
): ExtensionDetectedField[] {
  return fields.map((field) =>
    deriveLabelFromAttributes(field, resolveField(doc, field), attributeNames),
  );
}

/**
 * Warn when a page has cross-origin iframes.
 *
 * A content script only sees the frame it runs in. Rather than trying to reach into
 * other frames (which we will not do), we tell the user the form may be elsewhere.
 */
export function iframeWarning(doc: Document, platformName: string): string[] {
  const count = doc.querySelectorAll("iframe").length;
  if (count === 0) return [];
  return [
    `This ${platformName} page contains ${count} embedded frame(s). Fields inside a ` +
      "frame are not visible to the extension; open the form in its own tab if a " +
      "section appears to be missing.",
  ];
}
