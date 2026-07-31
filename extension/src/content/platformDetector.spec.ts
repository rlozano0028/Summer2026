/**
 * Tests for platform detection and adapter selection.
 *
 * The central claim being tested is the separation the whole design rests on: the URL
 * decides *identity* (and therefore whether confirmation is needed), while the DOM
 * decides which *adapter* reads the page. A Greenhouse-shaped page served from
 * loopback must come out as `local` and still be read by the Greenhouse adapter.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { selectAdapter } from "./adapters";
import { detectCurrentPlatform, getActiveAdapter, getPageSignals } from "./platformDetector";

/**
 * Point `window.location` at `url`.
 *
 * jsdom fixes the document URL at environment creation, so stubbing the global is the
 * only way to exercise several URLs in one file. `document.defaultView` is the same
 * object as `globalThis` in jsdom, so the detector sees the stub.
 */
function setPageUrl(url: string): void {
  vi.stubGlobal("location", new URL(url));
}

function setBody(html: string): void {
  document.body.innerHTML = html;
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

const GREENHOUSE_DOM = `
  <form id="application_form" class="application--form">
    <label for="email">Email</label>
    <input id="email" name="job_application[email]" type="email" />
    <input id="resume" name="job_application[resume]" type="file" />
    <textarea id="cover" name="job_application[cover_letter_text]"></textarea>
  </form>
`;

const WORKDAY_DOM = `
  <div data-automation-id="applyFlowPage">
    <form data-automation-id="applicationForm">
      <input data-automation-id="legalNameSection_firstName" id="first" type="text" />
      <input data-automation-id="email" id="email" type="email" />
      <textarea data-automation-id="shortAnswer" id="short"></textarea>
    </form>
  </div>
`;

const PLAIN_DOM = `
  <form id="job-application">
    <label for="email">Email</label>
    <input id="email" name="email" type="email" />
    <input id="resume" name="resume" type="file" />
    <textarea id="why" name="why"></textarea>
  </form>
`;

describe("selectAdapter", () => {
  it("picks the Greenhouse adapter from Greenhouse markup", () => {
    setBody(GREENHOUSE_DOM);
    expect(selectAdapter(document).adapter.platformId).toBe("greenhouse");
  });

  it("picks the Workday adapter from data-automation-id markup", () => {
    setBody(WORKDAY_DOM);
    expect(selectAdapter(document).adapter.platformId).toBe("workday");
  });

  it("falls back to the generic adapter on a plain form", () => {
    setBody(PLAIN_DOM);
    const { adapter, confidence } = selectAdapter(document);
    expect(adapter.platformId).toBe("generic");
    // The generic adapter must never sound confident: "it has a form" is weak.
    expect(confidence).toBeLessThan(0.6);
  });

  it("falls back to the generic adapter on a page with no form at all", () => {
    setBody("<main><h1>Job listing</h1><a href='/apply'>Apply</a></main>");
    expect(selectAdapter(document).adapter.platformId).toBe("generic");
  });
});

describe("detectCurrentPlatform", () => {
  it("reports a loopback fixture as local while using the vendor adapter", () => {
    setPageUrl("http://127.0.0.1:8000/test-fixtures/platform-pages/greenhouse-like.html");
    setBody(GREENHOUSE_DOM);

    const result = detectCurrentPlatform(document);

    expect(result.platform_id).toBe("local");
    expect(getActiveAdapter(document).platformId).toBe("greenhouse");
    expect(result.matched_by.some((entry) => entry.startsWith("page-signal:"))).toBe(true);
    expect(result.matched_by).toContain("url:local");
  });

  it("reports a real Greenhouse url as greenhouse", () => {
    setPageUrl("https://boards.greenhouse.io/acme/jobs/1");
    setBody(GREENHOUSE_DOM);

    expect(detectCurrentPlatform(document).platform_id).toBe("greenhouse");
  });

  it("reports an unrecognized host as unsupported, whatever the markup says", () => {
    setPageUrl("https://careers.unknown.example/apply");
    setBody(GREENHOUSE_DOM);

    const result = detectCurrentPlatform(document);
    expect(result.platform_id).toBe("unsupported");
  });

  it("warns when the url and the markup disagree", () => {
    setPageUrl("https://jobs.lever.co/acme/1");
    setBody(WORKDAY_DOM);

    const warnings = detectCurrentPlatform(document).warnings.join(" ");
    expect(warnings).toMatch(/Lever/);
    expect(warnings).toMatch(/Workday/);
  });

  it("warns about a password field without collecting anything from it", () => {
    setPageUrl("https://jobs.lever.co/acme/1");
    setBody(`${PLAIN_DOM}<input type="password" id="pw" name="pw" value="secret" />`);

    const result = detectCurrentPlatform(document);
    expect(result.signals.hasPasswordField).toBe(true);
    expect(result.warnings.join(" ")).toMatch(/never reads or fills passwords/);
    expect(JSON.stringify(result)).not.toContain("secret");
  });
});

describe("getPageSignals", () => {
  it("collects counts only, never page text or values", () => {
    setPageUrl("https://jobs.lever.co/acme/1");
    setBody(`
      <form>
        <input id="a" type="text" value="Ada Lovelace" />
        <input id="b" type="email" value="ada@example.com" />
        <input id="c" type="file" />
        <textarea id="d">A cover letter draft.</textarea>
      </form>
      <iframe src="https://example.com/embed"></iframe>
    `);

    const signals = getPageSignals(document);

    expect(signals.formCount).toBe(1);
    expect(signals.inputCount).toBe(4);
    expect(signals.fileInputCount).toBe(1);
    expect(signals.iframeCount).toBe(1);
    expect(signals.hasPasswordField).toBe(false);

    const serialized = JSON.stringify(signals);
    expect(serialized).not.toContain("Ada Lovelace");
    expect(serialized).not.toContain("ada@example.com");
    expect(serialized).not.toContain("cover letter");
  });
});
