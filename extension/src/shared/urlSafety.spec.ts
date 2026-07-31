/**
 * Tests for the URL rules.
 *
 * These mirror backend/tests/test_platform_allowlist.py deliberately: if the two
 * implementations ever disagree the extension will offer a button the backend
 * refuses, and that inconsistency should show up here first.
 */

import { describe, expect, it } from "vitest";

import {
  getDomain,
  getKnownPlatformForUrl,
  isInjectableUrl,
  isKnownSupportedPlatformUrl,
  isLocalUrl,
  isProbablyApplicationPage,
  shouldRequireRealPageConfirmation,
} from "./urlSafety";

describe("getDomain", () => {
  it("lowercases the host and drops the port", () => {
    expect(getDomain("https://BOARDS.Greenhouse.IO:443/acme")).toBe(
      "boards.greenhouse.io",
    );
  });

  it("returns an empty string for anything unparseable", () => {
    for (const value of ["", "   ", "not a url", "boards.greenhouse.io/acme"]) {
      expect(getDomain(value)).toBe("");
    }
  });
});

describe("isLocalUrl", () => {
  it("accepts the loopback origins", () => {
    expect(isLocalUrl("http://127.0.0.1:8000/sample-forms/basic.html")).toBe(true);
    expect(isLocalUrl("http://localhost:5173/")).toBe(true);
  });

  it("rejects a different port and a lookalike host", () => {
    expect(isLocalUrl("http://127.0.0.1:9999/")).toBe(false);
    expect(isLocalUrl("http://127.0.0.1.evil.example:8000/")).toBe(false);
  });

  it("rejects missing and malformed urls", () => {
    expect(isLocalUrl(undefined)).toBe(false);
    expect(isLocalUrl("")).toBe(false);
    expect(isLocalUrl("localhost:8000")).toBe(false);
  });
});

describe("getKnownPlatformForUrl", () => {
  it.each([
    ["https://boards.greenhouse.io/acme/jobs/1", "greenhouse"],
    ["https://greenhouse.io/acme", "greenhouse"],
    ["https://jobs.lever.co/acme/1", "lever"],
    ["https://jobs.ashbyhq.com/acme/1", "ashby"],
    ["https://acme.wd5.myworkdayjobs.com/en-US/careers", "workday"],
    ["https://acme.wd1.myworkdaysite.com/recruiting", "workday"],
    ["https://jobs.smartrecruiters.com/Acme/1", "smartrecruiters"],
  ])("identifies %s as %s", (url, expected) => {
    expect(getKnownPlatformForUrl(url)).toBe(expected);
    expect(isKnownSupportedPlatformUrl(url)).toBe(true);
  });

  it.each([
    "https://boards.greenhouse.io.evil.example/acme",
    "https://notgreenhouse.io/acme",
    "https://lever.co.attacker.test/acme",
    "https://myworkdayjobs.com.evil.test/job",
  ])("refuses the lookalike host %s", (url) => {
    expect(getKnownPlatformForUrl(url)).toBeNull();
    expect(isKnownSupportedPlatformUrl(url)).toBe(false);
  });

  it("requires https", () => {
    expect(getKnownPlatformForUrl("http://boards.greenhouse.io/acme")).toBeNull();
  });

  it("does not guess at company domains", () => {
    // Company domains are approved on the backend only, so the extension must not
    // claim to recognize one.
    expect(getKnownPlatformForUrl("https://careers.acme.example/apply")).toBeNull();
  });
});

describe("isInjectableUrl", () => {
  it("allows http and https only", () => {
    expect(isInjectableUrl("http://127.0.0.1:8000/x")).toBe(true);
    expect(isInjectableUrl("https://jobs.lever.co/acme")).toBe(true);
  });

  it.each([
    "chrome://extensions",
    "chrome-extension://abcdefghijklmnopabcdefghijklmnop/popup.html",
    "about:blank",
    "file:///C:/tmp/form.html",
    "view-source:https://example.com",
    "",
  ])("refuses %s", (url) => {
    expect(isInjectableUrl(url)).toBe(false);
  });
});

describe("isProbablyApplicationPage", () => {
  it("recognizes application-ish paths", () => {
    expect(isProbablyApplicationPage("https://acme.example/careers/apply")).toBe(true);
    expect(isProbablyApplicationPage("https://acme.example/jobs/42")).toBe(true);
  });

  it("does not fire on unrelated pages", () => {
    expect(isProbablyApplicationPage("https://acme.example/about-us")).toBe(false);
    expect(isProbablyApplicationPage("")).toBe(false);
  });
});

describe("shouldRequireRealPageConfirmation", () => {
  it("never requires confirmation on a loopback page", () => {
    expect(shouldRequireRealPageConfirmation("http://127.0.0.1:8000/x")).toBe(false);
  });

  it("requires confirmation on every other page, including unknown ones", () => {
    expect(shouldRequireRealPageConfirmation("https://jobs.lever.co/acme")).toBe(true);
    expect(shouldRequireRealPageConfirmation("https://who.knows.example/x")).toBe(true);
    // Failing closed matters most here: no URL must not mean "no confirmation".
    expect(shouldRequireRealPageConfirmation(undefined)).toBe(true);
  });
});
