/**
 * Tests for field detection.
 *
 * Detection decides what leaves the page, so these tests are mostly about omissions:
 * no passwords, no hidden inputs, no values. The rest cover the label plumbing real
 * forms need (aria-labelledby, fieldset legends) and the custom-control flag, since a
 * missed flag would let the backend believe a div is a text box.
 */

import { afterEach, describe, expect, it } from "vitest";

import { buildStableSelector, detectFields } from "./fieldDetector";

afterEach(() => {
  document.body.innerHTML = "";
});

describe("detectFields", () => {
  it("collects metadata but never a value", () => {
    document.body.innerHTML = `
      <label for="email">Email address</label>
      <input id="email" name="email" type="email" value="ada@example.com" required />
    `;
    const { fields } = detectFields(document);

    expect(fields).toHaveLength(1);
    expect(fields[0]).toMatchObject({
      selector: "#email",
      tag_name: "input",
      input_type: "email",
      name: "email",
      label_text: "Email address",
      required: true,
    });
    expect(JSON.stringify(fields)).not.toContain("ada@example.com");
  });

  it("skips password inputs and says so", () => {
    document.body.innerHTML = `
      <input id="email" type="email" />
      <input id="pw" type="password" value="hunter2" />
    `;
    const { fields, warnings } = detectFields(document);

    expect(fields.map((field) => field.id_attribute)).toEqual(["email"]);
    expect(warnings.join(" ")).toMatch(/never reads or fills passwords/);
    expect(JSON.stringify(fields)).not.toContain("hunter2");
  });

  it("skips hidden inputs", () => {
    document.body.innerHTML = `
      <input id="email" type="email" />
      <input id="csrf" type="hidden" name="csrf_token" value="abc123" />
    `;
    const { fields, warnings } = detectFields(document);

    expect(fields.map((field) => field.id_attribute)).toEqual(["email"]);
    expect(warnings.join(" ")).toMatch(/hidden field/);
  });

  it("resolves aria-labelledby when there is no label element", () => {
    document.body.innerHTML = `
      <span id="school_label">School</span>
      <input id="school" aria-labelledby="school_label" />
    `;
    expect(detectFields(document).fields[0].label_text).toBe("School");
  });

  it("prefixes a radio option with its fieldset legend", () => {
    document.body.innerHTML = `
      <fieldset>
        <legend>Are you legally authorized to work in this country?</legend>
        <input type="radio" id="yes" name="auth" value="yes" />
        <label for="yes">Yes</label>
      </fieldset>
    `;
    const field = detectFields(document).fields.find((f) => f.id_attribute === "yes")!;

    // Without the legend this reads as "Yes", which no mapper could classify as a
    // work-authorization question.
    expect(field.label_text).toMatch(/legally authorized/);
    expect(field.label_text).toMatch(/Yes/);
    expect(field.is_radio).toBe(true);
  });

  it("includes help and error text in the nearby context", () => {
    document.body.innerHTML = `
      <div class="field">
        <label for="phone">Phone</label>
        <input id="phone" aria-describedby="phone_help" />
        <span class="help" id="phone_help">Include your country code.</span>
        <span class="error">Enter a valid number.</span>
      </div>
    `;
    const nearby = detectFields(document).fields[0].nearby_text ?? "";

    expect(nearby).toMatch(/country code/);
    expect(nearby).toMatch(/valid number/);
    expect(nearby.length).toBeLessThanOrEqual(160);
  });

  it.each([
    ["<div id='f1' contenteditable='true'></div>", /rich-text/],
    ["<div id='f1' role='combobox'></div>", /combobox/],
    ["<div id='f1' role='listbox'></div>", /listbox/],
    ["<div id='f1' role='textbox'></div>", /textbox/],
  ])("flags %s as a custom control", (html, reason) => {
    document.body.innerHTML = html;
    const field = detectFields(document).fields[0];

    expect(field.is_custom_control).toBe(true);
    expect(field.unsupported_reason).toMatch(reason);
  });

  it("does not flag native inputs as custom controls", () => {
    document.body.innerHTML = `
      <input id="a" type="text" />
      <select id="b"><option>One</option></select>
      <textarea id="c"></textarea>
    `;
    for (const field of detectFields(document).fields) {
      expect(field.is_custom_control).toBe(false);
      expect(field.unsupported_reason).toBeNull();
    }
  });

  it("marks submit controls and file uploads", () => {
    document.body.innerHTML = `
      <input id="resume" type="file" />
      <button id="apply" type="submit">Apply</button>
    `;
    const byId = new Map(
      detectFields(document).fields.map((field) => [field.id_attribute, field]),
    );

    expect(byId.get("resume")!.is_file_upload).toBe(true);
    expect(byId.get("apply")!.is_submit_control).toBe(true);
  });

  it("collects select option labels", () => {
    document.body.innerHTML = `
      <select id="sponsorship"><option value="">Choose</option><option>Yes</option><option>No</option></select>
    `;
    expect(detectFields(document).fields[0].options).toEqual(["Choose", "Yes", "No"]);
  });

  it("warns when a page has no fields", () => {
    document.body.innerHTML = "<p>Nothing to fill here.</p>";
    const { fields, warnings } = detectFields(document);

    expect(fields).toEqual([]);
    expect(warnings.join(" ")).toMatch(/No form fields/);
  });

  it("returns fields in document order", () => {
    document.body.innerHTML = `
      <input id="first" />
      <div id="custom" role="combobox"></div>
      <input id="last" />
    `;
    expect(detectFields(document).fields.map((f) => f.id_attribute)).toEqual([
      "first",
      "custom",
      "last",
    ]);
  });
});

describe("buildStableSelector", () => {
  it("prefers a unique id", () => {
    document.body.innerHTML = "<input id='email' name='email' />";
    const el = document.getElementById("email")!;
    expect(buildStableSelector(el, 0, document)).toBe("#email");
  });

  it("falls back to a unique name", () => {
    document.body.innerHTML = "<input name='email' />";
    const el = document.querySelector("input")!;
    expect(buildStableSelector(el, 0, document)).toBe('input[name="email"]');
  });

  it("uses a platform test attribute when id and name are absent", () => {
    document.body.innerHTML = "<input data-automation-id='email' />";
    const el = document.querySelector("input")!;
    expect(buildStableSelector(el, 0, document)).toBe('[data-automation-id="email"]');
  });

  it("falls back to a structural path that still resolves", () => {
    document.body.innerHTML = "<div><input /><input /></div>";
    const el = document.querySelectorAll("input")[1];
    const selector = buildStableSelector(el, 1, document);

    expect(document.querySelector(selector)).toBe(el);
  });
});
