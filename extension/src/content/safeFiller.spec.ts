/**
 * Tests for the filler's refusals.
 *
 * This module is the last thing between a plan and a real application form, so the
 * tests are written as a list of things that must *not* happen. A passing "it filled
 * the name field" test is reassuring; a passing "it refused to touch the password
 * field" test is the one that matters.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { ACTION_FILL } from "../shared/constants";
import type { ExtensionFillInstruction } from "../shared/types";
import {
  applyFillInstructions,
  filterFillableInstructions,
  refusalReason,
} from "./safeFiller";

function instruction(
  overrides: Partial<ExtensionFillInstruction> = {},
): ExtensionFillInstruction {
  return {
    field_id: "f1",
    selector: "#f1",
    action: ACTION_FILL,
    value: "Ada Lovelace",
    value_preview: "Ada L...",
    field_type: "text",
    category: "identity.full_name",
    reason: "matched",
    ...overrides,
  };
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("filterFillableInstructions", () => {
  it("keeps only fill actions that carry a value", () => {
    const kept = filterFillableInstructions([
      instruction({ field_id: "keep" }),
      instruction({ field_id: "suggest", action: "suggest" }),
      instruction({ field_id: "manual", action: "manual_review" }),
      instruction({ field_id: "skip", action: "skip" }),
      instruction({ field_id: "null-value", value: null }),
      instruction({ field_id: "blank-value", value: "   " }),
    ]);

    expect(kept.map((item) => item.field_id)).toEqual(["keep"]);
  });
});

describe("refusalReason", () => {
  it.each([
    ["<input id='f1' type='password' />", /never filled/],
    ["<input id='f1' type='file' />", /never filled/],
    ["<input id='f1' type='submit' />", /never filled/],
    ["<input id='f1' type='hidden' />", /never filled/],
    ["<button id='f1'>Apply</button>", /button/],
    ["<input id='f1' type='checkbox' />", /manual review/],
    ["<input id='f1' type='radio' />", /manual review/],
    ["<input id='f1' type='text' disabled />", /disabled/],
    ["<input id='f1' type='text' readonly />", /readonly/],
    ["<div id='f1' contenteditable='true'></div>", /rich-text/],
    ["<div id='f1' role='combobox'></div>", /custom combobox widget/],
    ["<div id='f1' role='listbox'></div>", /custom listbox widget/],
    ["<div id='f1'>plain div</div>", /unsupported element/],
    ["<input id='f1' type='text' aria-disabled='true' />", /disabled/],
  ])("refuses %s", (html, expected) => {
    document.body.innerHTML = html;
    const el = document.getElementById("f1")!;
    expect(refusalReason(el)).toMatch(expected);
  });

  it("allows a plain text input, a textarea, and a select", () => {
    document.body.innerHTML = `
      <input id="a" type="text" />
      <textarea id="b"></textarea>
      <select id="c"><option>One</option></select>
    `;
    for (const id of ["a", "b", "c"]) {
      expect(refusalReason(document.getElementById(id)!)).toBeNull();
    }
  });
});

describe("applyFillInstructions", () => {
  it("fills a text input and reports it", () => {
    document.body.innerHTML = "<input id='f1' type='text' />";
    const result = applyFillInstructions([instruction()]);

    expect((document.getElementById("f1") as HTMLInputElement).value).toBe(
      "Ada Lovelace",
    );
    expect(result).toMatchObject({ filled: 1, failed: 0, skipped: 0 });
  });

  it("dispatches input, change, and blur so page frameworks notice", () => {
    document.body.innerHTML = "<input id='f1' type='text' />";
    const el = document.getElementById("f1")!;
    const seen: string[] = [];
    for (const type of ["input", "change", "blur"]) {
      el.addEventListener(type, () => seen.push(type));
    }

    applyFillInstructions([instruction()]);

    expect(seen).toEqual(["input", "change", "blur"]);
  });

  it("never clicks and never submits", () => {
    document.body.innerHTML = `
      <form id="form"><input id="f1" type="text" /><button type="submit">Apply</button></form>
    `;
    const form = document.getElementById("form") as HTMLFormElement;
    const submit = vi.fn((event: Event) => event.preventDefault());
    form.addEventListener("submit", submit);
    const click = vi.fn();
    form.querySelector("button")!.addEventListener("click", click);

    applyFillInstructions([instruction()]);

    expect(submit).not.toHaveBeenCalled();
    expect(click).not.toHaveBeenCalled();
  });

  it("leaves a password input untouched even when told to fill it", () => {
    document.body.innerHTML = "<input id='f1' type='password' />";
    const result = applyFillInstructions([instruction()]);

    expect((document.getElementById("f1") as HTMLInputElement).value).toBe("");
    expect(result.filled).toBe(0);
    expect(result.skipped).toBe(1);
  });

  it("leaves a checkbox unchecked", () => {
    document.body.innerHTML = "<input id='f1' type='checkbox' />";
    applyFillInstructions([instruction({ value: "Yes" })]);
    expect((document.getElementById("f1") as HTMLInputElement).checked).toBe(false);
  });

  it("does not write into a custom combobox", () => {
    document.body.innerHTML = "<div id='f1' role='combobox'>Select One</div>";
    const result = applyFillInstructions([instruction({ value: "United States" })]);

    expect(document.getElementById("f1")!.textContent).toBe("Select One");
    expect(result.skipped).toBe(1);
  });

  it("selects a matching option and refuses a non-matching one", () => {
    document.body.innerHTML = `
      <select id="f1"><option value="">Choose</option><option value="no">No</option></select>
    `;
    const el = document.getElementById("f1") as HTMLSelectElement;

    expect(applyFillInstructions([instruction({ value: "No" })]).filled).toBe(1);
    expect(el.value).toBe("no");

    el.value = "";
    const result = applyFillInstructions([instruction({ value: "Maybe" })]);
    expect(el.value).toBe("");
    expect(result.skipped).toBe(1);
    expect(result.warnings.join(" ")).toMatch(/no exact option match/);
  });

  it("reports a stale selector as failed rather than filling something else", () => {
    document.body.innerHTML = "<input id='other' type='text' />";
    const result = applyFillInstructions([instruction()]);

    expect((document.getElementById("other") as HTMLInputElement).value).toBe("");
    expect(result.failed).toBe(1);
    expect(result.warnings.join(" ")).toMatch(/Could not find/);
  });

  it("never puts a value into a warning message", () => {
    document.body.innerHTML = "<input id='f1' type='text' disabled />";
    const result = applyFillInstructions([instruction({ value: "super-secret" })]);

    expect(result.warnings.join(" ")).not.toContain("super-secret");
  });
});
