/**
 * Tests that the manifest stays as narrow as Phase 7 claims it is.
 *
 * The documented design is "no new host permissions: `activeTab` plus `scripting`,
 * injected on user click". That claim is easy to break accidentally - adding
 * `<all_urls>` while debugging is a one-line change that would silently turn this
 * into an extension that can read every page. These assertions make that change fail
 * the test suite instead.
 */

import { describe, expect, it } from "vitest";

import manifest from "../../public/manifest.json";
import {
  FORBIDDEN_HOST_PERMISSIONS,
  REQUIRED_PERMISSIONS,
  canAccessTabOnUserAction,
  describeTabAccessProblem,
} from "./permissions";

describe("manifest", () => {
  it("requests exactly the permissions Phase 7 relies on", () => {
    expect([...manifest.permissions].sort()).toEqual([...REQUIRED_PERMISSIONS].sort());
  });

  it("declares no broad host permissions", () => {
    for (const forbidden of FORBIDDEN_HOST_PERMISSIONS) {
      expect(manifest.host_permissions).not.toContain(forbidden);
    }
  });

  it("limits host permissions to loopback origins", () => {
    for (const host of manifest.host_permissions) {
      expect(host).toMatch(/^http:\/\/(127\.0\.0\.1|localhost):\d+\/\*$/);
    }
  });

  it("keeps declarative content scripts on loopback origins only", () => {
    for (const entry of manifest.content_scripts) {
      for (const match of entry.matches) {
        expect(match).toMatch(/^http:\/\/(127\.0\.0\.1|localhost):\d+\/\*$/);
      }
    }
  });

  it("does not request optional host permissions", () => {
    expect(manifest).not.toHaveProperty("optional_host_permissions");
    expect(manifest).not.toHaveProperty("optional_permissions");
  });
});

describe("canAccessTabOnUserAction", () => {
  it("accepts http(s) pages", () => {
    expect(canAccessTabOnUserAction("https://jobs.lever.co/acme")).toBe(true);
    expect(canAccessTabOnUserAction("http://127.0.0.1:8000/x")).toBe(true);
  });

  it("rejects browser-internal and local-file pages", () => {
    expect(canAccessTabOnUserAction("chrome://settings")).toBe(false);
    expect(canAccessTabOnUserAction("file:///C:/form.html")).toBe(false);
  });
});

describe("describeTabAccessProblem", () => {
  it("returns null when the tab is usable", () => {
    expect(describeTabAccessProblem("https://jobs.lever.co/acme")).toBeNull();
  });

  it("explains a missing tab and an unusable scheme differently", () => {
    expect(describeTabAccessProblem("")).toMatch(/No active tab/);
    expect(describeTabAccessProblem("chrome://settings")).toMatch(/http\(s\) pages/);
  });
});
