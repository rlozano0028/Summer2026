/**
 * Detect form fields on the current page (extension side).
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
 * metadata is read from them. Hidden inputs are skipped for the same reason: a
 * CSRF token is not a field a person fills in.
 *
 * Selector strategy, in priority order:
 *   1. `#id` when the id is unique on the page.
 *   2. `tag[name="..."]` when the name resolves to exactly one element.
 *   3. `[data-testid=...]` / `[data-test=...]` / `[data-automation-id=...]` when
 *      present and unique.
 *   4. An `nth-of-type` path from the document root.
 *
 * Phase 7 additions, all in service of real pages:
 *   - `aria-labelledby` / `aria-describedby` are resolved, because real forms
 *     frequently label a control with a separate element instead of a `<label>`.
 *   - The nearest `fieldset`/`legend` is read for radio and checkbox groups, whose
 *     individual labels ("Yes", "No") are meaningless without the question.
 *   - Custom controls (contenteditable regions, ARIA comboboxes, listboxes, and
 *     textboxes built from divs) are detected and flagged `is_custom_control`. They
 *     are reported so the user can see them in the plan, and refused everywhere
 *     else: the backend routes them to manual review and the filler will not write
 *     to them.
 *
 * Limitations: the index-based fallback is only as stable as the DOM. If the page
 * re-renders between "Detect fields" and "Apply safe fills" (a React form, a
 * wizard step change), a fallback selector can go stale and the fill is reported
 * as failed rather than applied to the wrong element. Radio groups are reported
 * as individual inputs; the backend defers them to manual review. Fields inside an
 * iframe or a closed shadow root are not visible here, and no attempt is made to
 * reach them.
 */

import type { ExtensionDetectedField } from "../shared/types";

const SUBMIT_INPUT_TYPES = new Set(["submit", "button", "reset", "image"]);
const NEARBY_TEXT_LIMIT = 160;

/** Native controls worth reporting. `input[type=hidden]` is excluded by filtering. */
const NATIVE_CONTROL_SELECTOR = "input, textarea, select, button";

/**
 * Elements that behave like inputs but are not.
 *
 * `role="textbox"` and friends on a div mean a framework owns the value, so writing
 * to the DOM would either be ignored or corrupt the framework's state.
 */
const CUSTOM_CONTROL_SELECTOR = [
  "[contenteditable='true']",
  "[contenteditable='']",
  "div[role='combobox']",
  "div[role='listbox']",
  "div[role='textbox']",
  "span[role='combobox']",
  "span[role='textbox']",
  "[role='combobox']:not(input):not(select)",
  "[role='listbox']:not(select)",
].join(", ");

function cssEscape(value: string): string {
  if (typeof CSS !== "undefined" && typeof CSS.escape === "function") {
    return CSS.escape(value);
  }
  return value.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
}

function shorten(text: string): string {
  const collapsed = text.replace(/\s+/g, " ").trim();
  return collapsed.length > NEARBY_TEXT_LIMIT
    ? collapsed.slice(0, NEARBY_TEXT_LIMIT)
    : collapsed;
}

/**
 * True when the environment actually computes layout.
 *
 * jsdom reports every rectangle as 0x0, so under test the rect check below would
 * declare every field invisible. Checking the body once tells us whether rect data
 * means anything on this page.
 */
function hasLayoutEngine(doc: Document): boolean {
  return (doc.body?.getBoundingClientRect().height ?? 0) > 0;
}

function isVisible(el: Element, doc: Document): boolean {
  if (el.hasAttribute("hidden")) return false;
  const style = doc.defaultView?.getComputedStyle(el);
  if (
    style &&
    (style.display === "none" ||
      style.visibility === "hidden" ||
      style.opacity === "0")
  ) {
    return false;
  }
  const rect = el.getBoundingClientRect();
  if (rect.width > 0 || rect.height > 0) return true;
  return !hasLayoutEngine(doc);
}

/** Text of the elements referenced by `attribute`, joined. Empty when absent. */
function textFromIdRefs(el: Element, attribute: string, doc: Document): string {
  const refs = (el.getAttribute(attribute) ?? "").trim();
  if (!refs) return "";
  const parts: string[] = [];
  for (const id of refs.split(/\s+/)) {
    const target = doc.getElementById(id);
    const text = target?.textContent?.trim();
    if (text) parts.push(text);
  }
  return shorten(parts.join(" "));
}

function labelTextFor(el: Element, doc: Document): string | null {
  const id = el.getAttribute("id");
  if (id) {
    const forLabel = doc.querySelector(`label[for="${cssEscape(id)}"]`);
    const text = forLabel?.textContent?.trim();
    if (text) return shorten(text);
  }
  const parentLabel = el.closest("label");
  const parentText = parentLabel?.textContent?.trim();
  if (parentText) return shorten(parentText);

  // Real forms often use aria-labelledby instead of a <label>.
  const ariaLabelled = textFromIdRefs(el, "aria-labelledby", doc);
  return ariaLabelled || null;
}

/**
 * The question a radio or checkbox belongs to.
 *
 * "Yes" on its own tells the mapper nothing; "Are you legally authorized to work
 * in this country? Yes" tells it everything, and in particular tells it this is a
 * sensitive field to be left alone.
 */
function groupLegendFor(el: Element): string {
  const fieldset = el.closest("fieldset");
  const legend = fieldset?.querySelector("legend");
  const text = legend?.textContent?.trim();
  return text ? shorten(text) : "";
}

/**
 * A short slice of context around the field: its wrapper text, plus any help or
 * error text and `aria-describedby` content.
 *
 * Capped at NEARBY_TEXT_LIMIT so we never ship a meaningful portion of the page
 * back to the backend; it exists purely to help classify a field whose label is
 * plain text rather than a `<label>` element.
 */
function nearbyTextFor(el: Element, doc: Document): string | null {
  const parts: string[] = [];

  const container = el.closest(".field, fieldset, div, p, li");
  if (container) {
    const text = (container.textContent ?? "").replace(/\s+/g, " ").trim();
    if (text) parts.push(text);
  }

  const described = textFromIdRefs(el, "aria-describedby", doc);
  if (described) parts.push(described);

  if (container) {
    for (const helper of Array.from(
      container.querySelectorAll(".help, .error, .hint, [role='alert']"),
    )) {
      const text = helper.textContent?.trim();
      if (text) parts.push(text);
    }
  }

  const legend = groupLegendFor(el);
  if (legend) parts.push(legend);

  const combined = shorten(parts.join(" "));
  return combined || null;
}

function isUnique(selector: string, doc: Document): boolean {
  try {
    return doc.querySelectorAll(selector).length === 1;
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

/** Attributes real platforms use as stable test hooks, most specific first. */
const TEST_ID_ATTRIBUTES = [
  "data-testid",
  "data-test",
  "data-automation-id",
  "data-qa",
] as const;

/** Build the most stable selector available for `el`. Exported for reuse/tests. */
export function buildStableSelector(
  el: Element,
  index: number,
  doc: Document = document,
): string {
  const id = el.getAttribute("id");
  if (id) {
    const candidate = `#${cssEscape(id)}`;
    if (isUnique(candidate, doc)) return candidate;
  }

  const tag = el.tagName.toLowerCase();
  const name = el.getAttribute("name");
  if (name) {
    const candidate = `${tag}[name="${cssEscape(name)}"]`;
    if (isUnique(candidate, doc)) return candidate;
  }

  for (const attribute of TEST_ID_ATTRIBUTES) {
    const value = el.getAttribute(attribute);
    if (!value) continue;
    const candidate = `[${attribute}="${cssEscape(value)}"]`;
    if (isUnique(candidate, doc)) return candidate;
  }

  return nthOfTypePath(el) || `${tag}:nth-of-type(${index + 1})`;
}

/** True for password inputs, which are skipped without reading any metadata. */
function isPasswordInput(el: Element): boolean {
  return (el.getAttribute("type") ?? "").toLowerCase() === "password";
}

/** True for hidden inputs, which are never user-facing fields. */
function isHiddenInput(el: Element): boolean {
  return (
    el.tagName.toLowerCase() === "input" &&
    (el.getAttribute("type") ?? "").toLowerCase() === "hidden"
  );
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

/** Why an element counts as a custom control, or null when it is a native input. */
function customControlReason(el: Element): string | null {
  const tag = el.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return null;

  const contentEditable = el.getAttribute("contenteditable");
  if (contentEditable === "true" || contentEditable === "") {
    return "rich-text editor (contenteditable), not a plain text field";
  }
  const role = (el.getAttribute("role") ?? "").toLowerCase();
  if (role === "combobox") return "custom dropdown (ARIA combobox)";
  if (role === "listbox") return "custom list picker (ARIA listbox)";
  if (role === "textbox") return "custom text widget (ARIA textbox)";
  return "custom control built from non-input elements";
}

function describeField(
  el: Element,
  index: number,
  doc: Document,
): ExtensionDetectedField {
  const tag = el.tagName.toLowerCase();
  const type = (el.getAttribute("type") ?? "").toLowerCase() || null;
  const unsupportedReason = customControlReason(el);
  const label = labelTextFor(el, doc);
  const legend = groupLegendFor(el);
  const isChoice = tag === "input" && (type === "checkbox" || type === "radio");

  return {
    field_id: `field-${index}`,
    selector: buildStableSelector(el, index, doc),
    tag_name: tag,
    input_type: type,
    name: el.getAttribute("name"),
    id_attribute: el.getAttribute("id") || null,
    placeholder: el.getAttribute("placeholder"),
    aria_label: el.getAttribute("aria-label"),
    // For a radio or checkbox, prefix the group's question: "Yes" alone is not a
    // label the mapper can classify, and misclassifying a legal question is exactly
    // the mistake that matters most.
    label_text: isChoice && legend ? shorten(`${legend} ${label ?? ""}`) : label,
    nearby_text: nearbyTextFor(el, doc),
    autocomplete: el.getAttribute("autocomplete"),
    required: el.hasAttribute("required") || el.getAttribute("aria-required") === "true",
    visible: isVisible(el, doc),
    disabled:
      (el as HTMLInputElement).disabled === true ||
      el.hasAttribute("disabled") ||
      el.getAttribute("aria-disabled") === "true",
    readonly:
      (el as HTMLInputElement).readOnly === true ||
      el.hasAttribute("readonly") ||
      el.getAttribute("aria-readonly") === "true",
    options: optionLabels(el),
    is_file_upload: tag === "input" && type === "file",
    is_submit_control: isSubmitControl(el, tag, type),
    is_textarea: tag === "textarea",
    is_select: tag === "select",
    is_checkbox: tag === "input" && type === "checkbox",
    is_radio: tag === "input" && type === "radio",
    is_custom_control: unsupportedReason !== null,
    unsupported_reason: unsupportedReason,
  };
}

/**
 * Collect metadata for every form control on the page.
 *
 * Returns the fields plus any warnings worth showing the user (for example, how
 * many password inputs were ignored).
 */
export function detectFields(doc: Document = document): {
  fields: ExtensionDetectedField[];
  warnings: string[];
} {
  const native = Array.from(doc.querySelectorAll(NATIVE_CONTROL_SELECTOR));
  const custom = Array.from(doc.querySelectorAll(CUSTOM_CONTROL_SELECTOR));

  // Document order keeps field ids and the popup's review list aligned with what
  // the user sees on the page. A Set removes the overlap between the two queries.
  const elements = Array.from(new Set([...native, ...custom])).sort((a, b) =>
    a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1,
  );

  const fields: ExtensionDetectedField[] = [];
  const warnings: string[] = [];
  let passwordsSkipped = 0;
  let hiddenSkipped = 0;
  let customControls = 0;

  elements.forEach((el, index) => {
    if (isPasswordInput(el)) {
      passwordsSkipped += 1;
      return;
    }
    if (isHiddenInput(el)) {
      hiddenSkipped += 1;
      return;
    }
    const field = describeField(el, index, doc);
    if (field.is_custom_control) customControls += 1;
    fields.push(field);
  });

  if (passwordsSkipped > 0) {
    warnings.push(
      `Skipped ${passwordsSkipped} password field(s); this extension never reads or fills passwords.`,
    );
  }
  if (hiddenSkipped > 0) {
    warnings.push(`Skipped ${hiddenSkipped} hidden field(s).`);
  }
  if (customControls > 0) {
    warnings.push(
      `${customControls} field(s) are custom controls (built from divs rather than ` +
        "inputs). They are listed for review but never filled automatically.",
    );
  }
  if (fields.length === 0) {
    warnings.push("No form fields were found on this page.");
  }

  return { fields, warnings };
}
