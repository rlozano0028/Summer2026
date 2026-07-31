/**
 * Visually mark fields on the page according to their mapping decision (Phase 6).
 *
 * Each highlighted field gets a coloured outline plus a small badge naming the
 * action. The badge tooltip carries the action, category, and reason so the user
 * can see *why* a decision was made without leaving the page.
 *
 * Privacy: badges and tooltips never show a profile value, not even the redacted
 * preview. Previews stay in the popup, which only the user can see.
 */

import { ACTION_FILL, ACTION_LABELS, ACTION_MANUAL_REVIEW, ACTION_SKIP, ACTION_SUGGEST } from "../shared/constants";
import type { FieldMapping } from "../shared/types";

const STYLE_ELEMENT_ID = "autofill-assistant-highlight-styles";
const BADGE_CLASS = "autofill-assistant-badge";
const OUTLINE_ATTRIBUTE = "data-autofill-assistant-action";

const ACTION_COLORS: Record<string, string> = {
  [ACTION_FILL]: "#1a7f37",
  [ACTION_SUGGEST]: "#9a6700",
  [ACTION_MANUAL_REVIEW]: "#0969da",
  [ACTION_SKIP]: "#6e7781",
};

function ensureStyles(): void {
  if (document.getElementById(STYLE_ELEMENT_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ELEMENT_ID;
  style.textContent = `
    [${OUTLINE_ATTRIBUTE}] {
      outline-offset: 1px !important;
    }
    ${Object.entries(ACTION_COLORS)
      .map(
        ([action, color]) => `
    [${OUTLINE_ATTRIBUTE}="${action}"] {
      outline: 2px solid ${color} !important;
    }
    .${BADGE_CLASS}[data-action="${action}"] {
      background: ${color};
    }`,
      )
      .join("\n")}
    .${BADGE_CLASS} {
      display: inline-block;
      margin-left: 6px;
      padding: 1px 6px;
      border-radius: 8px;
      font: 600 10px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif;
      color: #fff;
      vertical-align: middle;
      cursor: help;
      user-select: none;
    }
  `;
  document.head.appendChild(style);
}

function badgeLabel(mapping: FieldMapping): string {
  const base = ACTION_LABELS[mapping.action] ?? mapping.action;
  return mapping.sensitive ? `${base} - sensitive` : base;
}

function badgeTooltip(mapping: FieldMapping): string {
  const parts = [
    `Action: ${ACTION_LABELS[mapping.action] ?? mapping.action}`,
    `Category: ${mapping.category}`,
    `Confidence: ${(mapping.confidence ?? 0).toFixed(2)}`,
  ];
  if (mapping.sensitive) {
    parts.push("Sensitive / legal field: answer this yourself.");
  }
  if (mapping.reason) {
    parts.push(mapping.reason);
  }
  return parts.join("\n");
}

/** Remove every outline and badge this module added. Safe to call repeatedly. */
export function clearHighlights(): number {
  const badges = Array.from(document.querySelectorAll(`.${BADGE_CLASS}`));
  badges.forEach((badge) => badge.remove());

  const outlined = Array.from(document.querySelectorAll(`[${OUTLINE_ATTRIBUTE}]`));
  outlined.forEach((el) => el.removeAttribute(OUTLINE_ATTRIBUTE));

  document.getElementById(STYLE_ELEMENT_ID)?.remove();
  return outlined.length;
}

/**
 * Highlight each mapped field. Returns how many fields were marked.
 *
 * Existing highlights are cleared first so repeated calls do not stack badges.
 */
export function highlightFields(mappings: FieldMapping[]): number {
  clearHighlights();
  ensureStyles();

  let marked = 0;
  for (const mapping of mappings) {
    let el: Element | null;
    try {
      el = document.querySelector(mapping.selector);
    } catch {
      continue;
    }
    if (!el) continue;

    el.setAttribute(OUTLINE_ATTRIBUTE, mapping.action);

    const badge = document.createElement("span");
    badge.className = BADGE_CLASS;
    badge.dataset.action = mapping.action;
    badge.textContent = badgeLabel(mapping);
    badge.title = badgeTooltip(mapping);
    // Place the badge after the field so it does not overlap the input itself.
    el.parentElement?.insertBefore(badge, el.nextSibling);
    marked += 1;
  }
  return marked;
}
