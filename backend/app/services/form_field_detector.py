"""Detect form fields on a page using Playwright (Phase 4).

The heavy lifting is done by a chunk of JavaScript (:data:`DETECT_FIELDS_JS`)
that runs inside the page via ``page.evaluate()`` and returns a plain list of
dicts. The Python side simply wraps those dicts into :class:`FormField` models.

Selector strategy (in priority order), documented so the limitations are clear:
1. ``#id`` when the element has a unique-looking id.
2. ``[name="..."]`` when it has a name.
3. ``[data-testid="..."]`` / ``[data-test="..."]`` when present.
4. An ``nth-of-type`` based CSS fallback path from the body.

Limitations:
- Index-based fallbacks are only as stable as the page structure. If the DOM
  changes between detection and fill, a fallback selector can go stale. For the
  local sample forms this is not a concern because we detect and fill in the
  same session.
- Radio groups are reported as individual inputs; higher layers decide how to
  treat them (Phase 4 is conservative and defers them to manual review).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.models.automation import FormField

if TYPE_CHECKING:  # Avoid importing Playwright at module import time.
    from playwright.sync_api import Page


# JavaScript executed inside the page. Returns a list of field descriptors.
# Kept dependency-free (no external libraries) so it runs in any browser context.
DETECT_FIELDS_JS = r"""
() => {
  const SUBMIT_TYPES = new Set(["submit", "button", "reset", "image"]);

  function isVisible(el) {
    const style = window.getComputedStyle(el);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
      return false;
    }
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function cssEscape(value) {
    if (window.CSS && CSS.escape) {
      return CSS.escape(value);
    }
    return value.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
  }

  function labelText(el) {
    // 1. <label for="id">
    if (el.id) {
      const forLabel = document.querySelector(`label[for="${cssEscape(el.id)}"]`);
      if (forLabel && forLabel.textContent) {
        return forLabel.textContent.trim();
      }
    }
    // 2. Wrapping <label>
    const parentLabel = el.closest("label");
    if (parentLabel && parentLabel.textContent) {
      return parentLabel.textContent.trim();
    }
    return null;
  }

  function nearbyText(el) {
    // Best-effort: text of the closest containing wrapper, minus option text.
    const container = el.closest(".field, fieldset, div, p, li");
    if (!container) return null;
    let text = (container.textContent || "").replace(/\s+/g, " ").trim();
    if (text.length > 160) text = text.slice(0, 160);
    return text || null;
  }

  function stableSelector(el, index) {
    if (el.id) {
      return `#${cssEscape(el.id)}`;
    }
    const name = el.getAttribute("name");
    if (name) {
      return `${el.tagName.toLowerCase()}[name="${cssEscape(name)}"]`;
    }
    const testId = el.getAttribute("data-testid") || el.getAttribute("data-test");
    if (testId) {
      return `[data-testid="${cssEscape(testId)}"]`;
    }
    // Fallback: index-based path from body.
    const path = [];
    let node = el;
    while (node && node.nodeType === 1 && node.tagName.toLowerCase() !== "html") {
      const tag = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (!parent) {
        path.unshift(tag);
        break;
      }
      const sameTag = Array.from(parent.children).filter(
        (c) => c.tagName.toLowerCase() === tag
      );
      const idx = sameTag.indexOf(node) + 1;
      path.unshift(`${tag}:nth-of-type(${idx})`);
      node = parent;
    }
    return path.join(" > ") || `*:nth-of-type(${index + 1})`;
  }

  const elements = Array.from(
    document.querySelectorAll("input, textarea, select, button")
  );

  return elements.map((el, index) => {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute("type") || "").toLowerCase() || null;
    const isFile = tag === "input" && type === "file";
    const isSubmit =
      tag === "button"
        ? (el.getAttribute("type") || "submit").toLowerCase() !== "menu" &&
          ((el.getAttribute("type") || "submit").toLowerCase() === "submit" ||
            (el.getAttribute("type") || "").toLowerCase() === "button" ||
            (el.getAttribute("type") || "").toLowerCase() === "reset")
        : tag === "input" && SUBMIT_TYPES.has(type || "");

    let options = [];
    if (tag === "select") {
      options = Array.from(el.options).map((o) => o.value || o.textContent.trim());
    }

    return {
      field_id: `field-${index}`,
      selector: stableSelector(el, index),
      tag_name: tag,
      input_type: type,
      name: el.getAttribute("name"),
      id_attribute: el.id || null,
      placeholder: el.getAttribute("placeholder"),
      aria_label: el.getAttribute("aria-label"),
      label_text: labelText(el),
      nearby_text: nearbyText(el),
      autocomplete: el.getAttribute("autocomplete"),
      required: el.hasAttribute("required"),
      visible: isVisible(el),
      disabled: el.disabled === true || el.hasAttribute("disabled"),
      readonly: el.readOnly === true || el.hasAttribute("readonly"),
      options: options,
      is_file_upload: isFile,
      is_submit_control: isSubmit,
    };
  });
}
"""


def detect_form_fields(page: "Page") -> list[FormField]:
    """Run the detection JS in the page and return typed :class:`FormField`s."""

    raw_fields: list[dict[str, Any]] = page.evaluate(DETECT_FIELDS_JS)
    return [FormField(**field) for field in raw_fields]
