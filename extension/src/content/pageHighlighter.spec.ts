/**
 * Tests for the page highlighter.
 *
 * Two properties matter: badges must never leak a value onto the page (anyone
 * looking over the user's shoulder can read the page, but not the popup), and
 * clearing must restore the DOM exactly, because the highlighter wraps elements to
 * position badges and a leftover wrapper would change a real page's layout.
 */

import { afterEach, describe, expect, it } from "vitest";

import { ACTION_FILL, ACTION_MANUAL_REVIEW } from "../shared/constants";
import type { FieldMapping } from "../shared/types";
import { clearHighlights, highlightFields } from "./pageHighlighter";

function mapping(overrides: Partial<FieldMapping> = {}): FieldMapping {
  return {
    field_id: "f1",
    selector: "#f1",
    profile_path: "identity.email",
    value_preview: "ad***@example.com",
    confidence: 0.92,
    action: ACTION_FILL,
    reason: "Matched label text 'Email'",
    sensitive: false,
    missing_value: false,
    category: "identity.email",
    evidence: [],
    warnings: [],
    field_fingerprint: "fp",
    ...overrides,
  };
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("highlightFields", () => {
  it("marks each mapped field and reports the count", () => {
    document.body.innerHTML = "<input id='f1' /><input id='f2' />";
    const marked = highlightFields(
      [mapping(), mapping({ field_id: "f2", selector: "#f2" })],
      [],
      document,
    );

    expect(marked).toBe(2);
    expect(
      document.querySelectorAll("[data-autofill-assistant-action]").length,
    ).toBe(2);
    expect(document.querySelectorAll(".autofill-assistant-badge").length).toBe(2);
  });

  it("never renders a value or a preview on the page", () => {
    document.body.innerHTML = "<input id='f1' />";
    highlightFields([mapping()], [], document);

    const badge = document.querySelector(".autofill-assistant-badge")!;
    expect(badge.textContent).toBe("Fill");
    expect(document.body.innerHTML).not.toContain("ad***@example.com");
    expect(badge.getAttribute("title")).not.toContain("ad***@example.com");
  });

  it("shows a custom control as unsupported rather than as its plan action", () => {
    document.body.innerHTML = "<div id='f1' role='combobox'></div>";
    highlightFields([mapping({ action: ACTION_MANUAL_REVIEW })], ["f1"], document);

    const el = document.getElementById("f1")!;
    expect(el.getAttribute("data-autofill-assistant-action")).toBe("unsupported");
    expect(document.querySelector(".autofill-assistant-badge")!.textContent).toBe(
      "Not supported",
    );
  });

  it("marks a sensitive field as such", () => {
    document.body.innerHTML = "<input id='f1' />";
    highlightFields(
      [mapping({ action: ACTION_MANUAL_REVIEW, sensitive: true })],
      [],
      document,
    );
    expect(document.querySelector(".autofill-assistant-badge")!.textContent).toContain(
      "sensitive",
    );
  });

  it("does not stack badges when called repeatedly", () => {
    document.body.innerHTML = "<input id='f1' />";
    highlightFields([mapping()], [], document);
    highlightFields([mapping()], [], document);

    expect(document.querySelectorAll(".autofill-assistant-badge").length).toBe(1);
  });

  it("ignores a selector that matches nothing and one that is invalid", () => {
    document.body.innerHTML = "<input id='f1' />";
    const marked = highlightFields(
      [
        mapping({ selector: "#missing" }),
        mapping({ field_id: "f2", selector: "input[[broken" }),
      ],
      [],
      document,
    );
    expect(marked).toBe(0);
  });
});

describe("clearHighlights", () => {
  it("restores the original DOM exactly", () => {
    const original = "<div class=\"field\"><label>Email</label><input id=\"f1\"></div>";
    document.body.innerHTML = original;

    highlightFields([mapping()], [], document);
    expect(document.body.innerHTML).not.toBe(original);

    const cleared = clearHighlights(document);

    expect(cleared).toBe(1);
    expect(document.body.innerHTML).toBe(original);
    expect(document.querySelector("style#autofill-assistant-highlight-styles")).toBeNull();
  });

  it("is safe to call when nothing is highlighted", () => {
    document.body.innerHTML = "<input id='f1' />";
    expect(clearHighlights(document)).toBe(0);
    expect(clearHighlights(document)).toBe(0);
  });
});
