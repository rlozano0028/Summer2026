/**
 * Visually mark fields on the page according to their mapping decision.
 *
 * Each highlighted field gets a coloured outline plus a small badge naming the
 * action. The badge tooltip carries the action, category, and reason so the user
 * can see *why* a decision was made without leaving the page.
 *
 * Privacy: badges and tooltips never show a profile value, not even the redacted
 * preview. Previews stay in the popup, which only the user can see.
 *
 * Phase 7 changes, both driven by real pages being less forgiving than a sample
 * form:
 *
 * - An `unsupported` state, used for custom controls, so "we will not touch this"
 *   reads differently from "we chose not to fill this".
 * - Badges are positioned defensively. Inserting an inline element into a real
 *   layout can push things around, so badges are absolutely positioned out of flow
 *   and the outline is drawn with `box-shadow`, which does not affect layout at all.
 */

import {
  ACTION_FILL,
  ACTION_LABELS,
  ACTION_MANUAL_REVIEW,
  ACTION_SKIP,
  ACTION_SUGGEST,
} from "../shared/constants";
import type { FieldMapping } from "../shared/types";

const STYLE_ELEMENT_ID = "autofill-assistant-highlight-styles";
const BADGE_CLASS = "autofill-assistant-badge";
const WRAPPER_CLASS = "autofill-assistant-badge-anchor";
const OUTLINE_ATTRIBUTE = "data-autofill-assistant-action";

/** Pseudo-actions: controls the extension refuses to modify, and sensitive fields. */
export const STATE_UNSUPPORTED = "unsupported";
const STATE_PROTECTED = "protected";

// Same palette as the popup and dashboard (see popup.css).
const ACTION_COLORS: Record<string, string> = {
  [ACTION_FILL]: "#1f7045",
  [ACTION_SUGGEST]: "#1e6474",
  [ACTION_MANUAL_REVIEW]: "#8a5300",
  [ACTION_SKIP]: "#5b6474",
  [STATE_UNSUPPORTED]: "#8a5300",
  [STATE_PROTECTED]: "#5e3f93",
};

const STATE_LABELS: Record<string, string> = {
  ...ACTION_LABELS,
  [STATE_UNSUPPORTED]: "Not supported",
  [STATE_PROTECTED]: "Protected",
};

function ensureStyles(doc: Document): void {
  if (doc.getElementById(STYLE_ELEMENT_ID)) return;
  const style = doc.createElement("style");
  style.id = STYLE_ELEMENT_ID;
  style.textContent = `
    [${OUTLINE_ATTRIBUTE}] {
      /* box-shadow instead of outline: it never participates in layout, so a
         highlighted field cannot shift a real page's design. */
      box-shadow: 0 0 0 2px currentColor inset !important;
    }
    ${Object.entries(ACTION_COLORS)
      .map(
        ([action, color]) => `
    [${OUTLINE_ATTRIBUTE}="${action}"] {
      box-shadow: 0 0 0 2px ${color} !important;
    }
    .${BADGE_CLASS}[data-action="${action}"] {
      background: ${color};
    }`,
      )
      .join("\n")}
    .${WRAPPER_CLASS} {
      position: relative !important;
      display: inline-block;
    }
    .${BADGE_CLASS} {
      position: absolute;
      top: -9px;
      right: -6px;
      z-index: 2147483647;
      padding: 1px 6px;
      border-radius: 8px;
      font: 600 10px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif;
      color: #fff;
      white-space: nowrap;
      pointer-events: auto;
      cursor: help;
      user-select: none;
    }
  `;
  (doc.head ?? doc.documentElement).appendChild(style);
}

/** The state a mapping should be shown as: its action, or `unsupported`. */
function stateFor(mapping: FieldMapping, unsupportedIds: Set<string>): string {
  if (mapping.sensitive) return STATE_PROTECTED;
  return unsupportedIds.has(mapping.field_id) ? STATE_UNSUPPORTED : mapping.action;
}

function badgeLabel(mapping: FieldMapping, state: string): string {
  const base = STATE_LABELS[state] ?? state;
  return mapping.sensitive ? `${base} (sensitive)` : base;
}

function badgeTooltip(mapping: FieldMapping, state: string): string {
  const parts = [
    `Action: ${STATE_LABELS[state] ?? state}`,
    `Category: ${mapping.category}`,
    `Confidence: ${(mapping.confidence ?? 0).toFixed(2)}`,
  ];
  if (state === STATE_UNSUPPORTED) {
    parts.push("This control cannot be filled automatically; fill it yourself.");
  }
  if (mapping.sensitive) {
    parts.push("Sensitive / legal field: answer this yourself.");
  }
  if (mapping.reason) {
    parts.push(mapping.reason);
  }
  return parts.join("\n");
}

/**
 * Attach a badge next to `el` without disturbing the page's layout.
 *
 * The badge is absolutely positioned inside a relatively positioned anchor. When the
 * field's parent can host it directly we use the parent; otherwise we wrap the field
 * in a span, which is removed again by `clearHighlights`.
 */
function attachBadge(el: Element, badge: HTMLElement, doc: Document): void {
  const parent = el.parentElement;
  if (!parent) return;

  const view = doc.defaultView;
  const parentPosition = view ? view.getComputedStyle(parent).position : "static";
  if (parentPosition !== "static") {
    parent.appendChild(badge);
    return;
  }

  const anchor = doc.createElement("span");
  anchor.className = WRAPPER_CLASS;
  parent.insertBefore(anchor, el);
  anchor.appendChild(el);
  anchor.appendChild(badge);
}

/** Remove every outline, badge, and anchor this module added. Idempotent. */
export function clearHighlights(doc: Document = document): number {
  Array.from(doc.querySelectorAll(`.${BADGE_CLASS}`)).forEach((badge) =>
    badge.remove(),
  );

  // Unwrap anchors, putting each field back where it was.
  Array.from(doc.querySelectorAll(`.${WRAPPER_CLASS}`)).forEach((anchor) => {
    const parent = anchor.parentElement;
    if (!parent) return;
    while (anchor.firstChild) parent.insertBefore(anchor.firstChild, anchor);
    anchor.remove();
  });

  const outlined = Array.from(doc.querySelectorAll(`[${OUTLINE_ATTRIBUTE}]`));
  outlined.forEach((el) => el.removeAttribute(OUTLINE_ATTRIBUTE));

  doc.getElementById(STYLE_ELEMENT_ID)?.remove();
  return outlined.length;
}

/**
 * Highlight each mapped field. Returns how many fields were marked.
 *
 * Existing highlights are cleared first so repeated calls do not stack badges.
 * `unsupportedFieldIds` marks fields the extension refuses to modify, which are
 * shown differently from fields it merely chose not to fill.
 */
export function highlightFields(
  mappings: FieldMapping[],
  unsupportedFieldIds: string[] = [],
  doc: Document = document,
): number {
  clearHighlights(doc);
  ensureStyles(doc);

  const unsupportedIds = new Set(unsupportedFieldIds);
  let marked = 0;
  for (const mapping of mappings) {
    let el: Element | null;
    try {
      el = doc.querySelector(mapping.selector);
    } catch {
      continue;
    }
    if (!el) continue;

    const state = stateFor(mapping, unsupportedIds);
    el.setAttribute(OUTLINE_ATTRIBUTE, state);

    const badge = doc.createElement("span");
    badge.className = BADGE_CLASS;
    badge.dataset.action = state;
    badge.textContent = badgeLabel(mapping, state);
    badge.title = badgeTooltip(mapping, state);
    attachBadge(el, badge, doc);
    marked += 1;
  }
  return marked;
}
