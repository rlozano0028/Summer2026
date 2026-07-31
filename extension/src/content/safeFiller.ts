/**
 * Apply approved fill instructions to the page.
 *
 * This module is the last safety gate before the DOM is touched. The backend
 * already refuses to send a value for anything unsafe, but every check is
 * repeated here so a bug or a tampered response still cannot cause a bad fill.
 *
 * Hard rules, unchanged from Phase 6 and still enforced on real pages:
 * - Only `action === "fill"` instructions that carry a non-empty value are applied.
 * - Passwords, file inputs, submit controls, disabled, readonly, and hidden
 *   elements are never touched.
 * - Checkboxes and radios are never toggled.
 * - Custom controls (contenteditable, ARIA combobox/listbox/textbox) are never
 *   touched: their value belongs to framework state we cannot set correctly.
 * - Selects only change on an exact normalized option match.
 * - Nothing is ever clicked, and no form is ever submitted.
 *
 * The one Phase 7 addition is a `blur` event after a successful fill, because real
 * platforms commonly validate on blur and a field left un-blurred can look invalid
 * to the user even though the value is correct.
 */

import {
  ACTION_FILL,
  NEVER_FILL_INPUT_TYPES,
} from "../shared/constants";
import type { ApplyFillResult, ExtensionFillInstruction } from "../shared/types";

type Fillable = HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;

/** Keep only instructions this module is willing to act on. Exported for tests. */
export function filterFillableInstructions(
  instructions: ExtensionFillInstruction[],
): ExtensionFillInstruction[] {
  return instructions.filter(
    (instruction) =>
      instruction.action === ACTION_FILL &&
      typeof instruction.value === "string" &&
      instruction.value.trim().length > 0,
  );
}

function normalize(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

function resolveElement(selector: string): Element | null {
  try {
    return document.querySelector(selector);
  } catch {
    return null;
  }
}

/**
 * Reasons an element must not be written to, or null when it is safe.
 *
 * Mirrors the backend's gating so the two cannot disagree silently.
 */
export function refusalReason(el: Element): string | null {
  const tag = el.tagName.toLowerCase();
  if (tag === "button") return "element is a button";

  const type = (el.getAttribute("type") ?? "").toLowerCase();
  if (NEVER_FILL_INPUT_TYPES.has(type)) return `input type "${type}" is never filled`;

  // Custom controls are named before the generic tag check so the reason shown to
  // the user says what the element actually is.
  if (el.hasAttribute("contenteditable")) {
    return "element is a rich-text editor";
  }
  const role = (el.getAttribute("role") ?? "").toLowerCase();
  if (role === "combobox" || role === "listbox" || role === "textbox") {
    return `element is a custom ${role} widget`;
  }
  // Anything that is not a native input is out of scope, whatever it looks like.
  if (tag !== "input" && tag !== "textarea" && tag !== "select") {
    return `unsupported element <${tag}>`;
  }

  const input = el as HTMLInputElement;
  if (input.disabled || el.hasAttribute("disabled") || el.getAttribute("aria-disabled") === "true") {
    return "element is disabled";
  }
  if (input.readOnly || el.hasAttribute("readonly") || el.getAttribute("aria-readonly") === "true") {
    return "element is readonly";
  }
  if (type === "checkbox" || type === "radio") {
    return "checkboxes and radios are always left for manual review";
  }
  return null;
}

/**
 * Write a value and notify page frameworks.
 *
 * React and similar libraries track the value via a property setter on the
 * element's prototype, so assigning `el.value` directly can be silently
 * reverted. Using the native setter plus `input`/`change` events keeps
 * controlled components in sync.
 */
function setValueWithEvents(el: HTMLInputElement | HTMLTextAreaElement, value: string): void {
  const prototype =
    el instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  if (setter) {
    setter.call(el, value);
  } else {
    el.value = value;
  }
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  // Many real forms validate on blur; without this the field can be shown as
  // invalid even though the value is correct.
  el.dispatchEvent(new Event("blur", { bubbles: false }));
}

/** Select an option only on an exact normalized match. Returns false otherwise. */
function selectExactOption(el: HTMLSelectElement, value: string): boolean {
  const target = normalize(value);
  const match = Array.from(el.options).find(
    (option) =>
      normalize(option.value) === target ||
      normalize(option.textContent ?? "") === target,
  );
  if (!match) return false;
  el.value = match.value;
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
  el.dispatchEvent(new Event("blur", { bubbles: false }));
  return true;
}

/**
 * Apply the safe subset of `instructions` to the page.
 *
 * Never clicks, never submits, and never throws: every problem is reported in the
 * returned counts and warnings so the popup can show the user what happened.
 */
export function applyFillInstructions(
  instructions: ExtensionFillInstruction[],
): ApplyFillResult {
  const fillable = filterFillableInstructions(instructions);
  const result: ApplyFillResult = {
    filled: 0,
    failed: 0,
    skipped: instructions.length - fillable.length,
    warnings: [],
  };

  for (const instruction of fillable) {
    const el = resolveElement(instruction.selector);
    if (!el) {
      result.failed += 1;
      result.warnings.push(
        `Could not find "${instruction.selector}" on the page; the form may have changed since detection.`,
      );
      continue;
    }

    const refusal = refusalReason(el);
    if (refusal) {
      result.skipped += 1;
      result.warnings.push(`Skipped "${instruction.selector}": ${refusal}.`);
      continue;
    }

    const value = instruction.value as string;
    const element = el as Fillable;
    try {
      if (element instanceof HTMLSelectElement) {
        if (selectExactOption(element, value)) {
          result.filled += 1;
        } else {
          result.skipped += 1;
          result.warnings.push(
            `Skipped "${instruction.selector}": no exact option match, choose it manually.`,
          );
        }
        continue;
      }
      setValueWithEvents(element as HTMLInputElement | HTMLTextAreaElement, value);
      result.filled += 1;
    } catch (error) {
      result.failed += 1;
      result.warnings.push(
        `Failed to fill "${instruction.selector}": ${
          error instanceof Error ? error.message : String(error)
        }`,
      );
    }
  }

  return result;
}
