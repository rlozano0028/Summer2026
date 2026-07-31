/**
 * Detect form fields on the current page (Phase 6, extension side).
 *
 * This is deliberately a separate implementation from the Playwright detector in
 * backend/app/services/form_field_detector.py: that one runs inside a
 * Playwright-controlled browser and stays owned by Phase 4. The two produce the
 * same metadata shape so the Phase 5 mapping engine treats them identically.
 *
 * What is collected: only structural metadata (tag, type, name, id, placeholder,
 * aria-label, autocomplete, label text, a short slice of nearby text, select
 * option labels, and boolean state flags).
 *
 * What is never collected: element values, page HTML, full page text, or
 * anything about password inputs - those are skipped entirely, before any
 * metadata is read from them.
 *
 * Selector strategy, in priority order:
 *   1. `#id` when the id is unique on the page.
 *   2. `tag[name="..."]` when the name resolves to exactly one element.
 *   3. `[data-testid=...]` / `[data-test=...]` when present and unique.
 *   4. An `nth-of-type` path from the document root.
 *
 * Limitations: the index-based fallback is only as stable as the DOM. If the page
 * re-renders between "Detect fields" and "Apply safe fills" (a React form, a
 * wizard step change), a fallback selector can go stale and the fill is reported
 * as failed rather than applied to the wrong element. Radio groups are reported
 * as individual inputs; the backend defers them to manual review.
 */

import type { ExtensionDetectedField } from "../shared/types";

const SUBMIT_INPUT_TYPES = new Set(["submit", "button", "reset", "image"]);
const NEARBY_TEXT_LIMIT = 160;

function cssEscape(value: string): string {
  if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
    return CSS.escape(value);
  }
  return value.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
}

function isVisible(el: Element): boolean {
  const style = window.getComputedStyle(el);
  if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
    return false;
  }
  const rect = el.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

function labelTextFor(el: Element): string | null {
  const id = el.getAttribute("id");
  if (id) {
    const forLabel = document.querySelector(`label[for="${cssEscape(id)}"]`);
    const text = forLabel?.textContent?.trim();
    if (text) return text;
  }
  const parentLabel = el.closest("label");
  const parentText = parentLabel?.textContent?.trim();
  return parentText || null;
}

/**
 * A short slice of the text of the field's immediate wrapper.
 *
 * Capped at NEARBY_TEXT_LIMIT characters so we never ship a meaningful portion of
 * the page back to the backend; it exists purely to help classify a field whose
 * label is text rather than a <label> element.
 */
function nearbyTextFor(el: Element): string | null {
  const container = el.closest(".field, fieldset, div, p, li");
  if (!container) return null;
  const text = (container.textContent ?? "").replace(/\s+/g, " ").trim();
  if (!text) return null;
  return text.length > NEARBY_TEXT_LIMIT ? text.slice(0, NEARBY_TEXT_LIMIT) : text;
}

function isUnique(selector: string): boolean {
  try {
    return document.querySelectorAll(selector).length === 1;
  } catch {
    return false;
  }
}

function nthOfTypePath(el: Element): string {
  const path: string[] = [];
  let node: Element | null = el;
  while (node && node.nodeType === 1 && node.tagName.toLowerCase() !== "html") {
    const tag = node.tagName.toLowerCase();
    const parent: Element | null = node.parentElement;
    if (!parent) {
      path.unshift(tag);
      break;
    }
    const sameTag = Array.from(parent.children).filter(
      (child) => child.tagName.toLowerCase() === tag,
    );
    path.unshift(`${tag}:nth-of-type(${sameTag.indexOf(node) + 1})`);
    node = parent;
  }
  return path.join(" > ");
}

/** Build the most stable selector available for `el`. Exported for reuse/tests. */
export function buildStableSelector(el: Element, index: number): string {
  const id = el.getAttribute("id");
  if (id) {
    const candidate = `#${cssEscape(id)}`;
    if (isUnique(candidate)) return candidate;
  }

  const tag = el.tagName.toLowerCase();
  const name = el.getAttribute("name");
  if (name) {
    const candidate = `${tag}[name="${cssEscape(name)}"]`;
    if (isUnique(candidate)) return candidate;
  }

  const testId = el.getAttribute("data-testid") ?? el.getAttribute("data-test");
  if (testId) {
    const attr = el.hasAttribute("data-testid") ? "data-testid" : "data-test";
    const candidate = `[${attr}="${cssEscape(testId)}"]`;
    if (isUnique(candidate)) return candidate;
  }

  return nthOfTypePath(el) || `${tag}:nth-of-type(${index + 1})`;
}

/** True for password inputs, which are skipped without reading any metadata. */
function isPasswordInput(el: Element): boolean {
  return (el.getAttribute("type") ?? "").toLowerCase() === "password";
}

function isSubmitControl(el: Element, tag: string, type: string | null): boolean {
  if (tag === "button") {
    // A <button> defaults to type="submit" when the attribute is absent.
    const buttonType = (el.getAttribute("type") ?? "submit").toLowerCase();
    return buttonType === "submit" || buttonType === "button" || buttonType === "reset";
  }
  return tag === "input" && SUBMIT_INPUT_TYPES.has(type ?? "");
}

function optionLabels(el: Element): string[] {
  if (el.tagName.toLowerCase() !== "select") return [];
  return Array.from((el as HTMLSelectElement).options).map(
    (option) => option.value || (option.textContent ?? "").trim(),
  );
}

/**
 * Collect metadata for every form control on the page.
 *
 * Returns the fields plus any warnings worth showing the user (for example, how
 * many password inputs were ignored).
 */
export function detectFields(): {
  fields: ExtensionDetectedField[];
  warnings: string[];
} {
  const elements = Array.from(
    document.querySelectorAll("input, textarea, select, button"),
  );
  const fields: ExtensionDetectedField[] = [];
  const warnings: string[] = [];
  let passwordsSkipped = 0;

  elements.forEach((el, index) => {
    if (isPasswordInput(el)) {
      passwordsSkipped += 1;
      return;
    }

    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute("type") ?? "").toLowerCase() || null;

    fields.push({
      field_id: `field-${index}`,
      selector: buildStableSelector(el, index),
      tag_name: tag,
      input_type: type,
      name: el.getAttribute("name"),
      id_attribute: el.getAttribute("id") || null,
      placeholder: el.getAttribute("placeholder"),
      aria_label: el.getAttribute("aria-label"),
      label_text: labelTextFor(el),
      nearby_text: nearbyTextFor(el),
      autocomplete: el.getAttribute("autocomplete"),
      required: el.hasAttribute("required"),
      visible: isVisible(el),
      disabled:
        (el as HTMLInputElement).disabled === true || el.hasAttribute("disabled"),
      readonly:
        (el as HTMLInputElement).readOnly === true || el.hasAttribute("readonly"),
      options: optionLabels(el),
      is_file_upload: tag === "input" && type === "file",
      is_submit_control: isSubmitControl(el, tag, type),
      is_textarea: tag === "textarea",
      is_select: tag === "select",
      is_checkbox: tag === "input" && type === "checkbox",
      is_radio: tag === "input" && type === "radio",
    });
  });

  if (passwordsSkipped > 0) {
    warnings.push(
      `Skipped ${passwordsSkipped} password field(s); this extension never reads or fills passwords.`,
    );
  }
  if (fields.length === 0) {
    warnings.push("No form fields were found on this page.");
  }

  return { fields, warnings };
}
