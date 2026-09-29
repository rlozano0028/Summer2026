import { describe, expect, it } from "vitest";

import type { ExtensionDetectedField, FieldMapping, FillPlan } from "../shared/types";
import { buildReview, confidenceLevel, stepState, type StepInput } from "./decisions";

function mapping(overrides: Partial<FieldMapping>): FieldMapping {
  return {
    field_id: "f1",
    selector: "#f1",
    profile_path: null,
    value_preview: null,
    confidence: 0.95,
    action: "fill",
    reason: "",
    sensitive: false,
    missing_value: false,
    category: "identity.email",
    evidence: [],
    warnings: [],
    field_fingerprint: "",
    ...overrides,
  };
}

function plan(mappings: FieldMapping[]): FillPlan {
  return {
    form_name: "x",
    form_url: "http://127.0.0.1:8000/x",
    generated_at: "",
    mappings,
    warnings: [],
    manual_review_count: 0,
    fill_count: 0,
    suggest_count: 0,
    skip_count: 0,
  };
}

function field(id: string, extra: Partial<ExtensionDetectedField> = {}) {
  return { field_id: id, label_text: `Label ${id}`, ...extra } as ExtensionDetectedField;
}

describe("buildReview", () => {
  it("puts sensitive fields in Protected whatever the action says", () => {
    const review = buildReview(
      plan([mapping({ field_id: "a", sensitive: true, action: "fill" })]),
      [field("a")],
    );
    expect(review.protected).toHaveLength(1);
    expect(review.fill).toHaveLength(0);
  });

  it("never lists an unsupported custom control under Will fill", () => {
    const review = buildReview(
      plan([mapping({ field_id: "a", action: "fill" })]),
      [field("a", { is_custom_control: true })],
    );
    expect(review.fill).toHaveLength(0);
    expect(review.manual_review[0].unsupported).toBe(true);
  });

  it("groups plain decisions by action and uses the visible label", () => {
    const review = buildReview(
      plan([
        mapping({ field_id: "a", action: "fill" }),
        mapping({ field_id: "b", action: "suggest" }),
        mapping({ field_id: "c", action: "skip" }),
        mapping({ field_id: "d", action: "bogus" as FieldMapping["action"] }),
      ]),
      [field("a"), field("b"), field("c"), field("d")],
    );
    expect(review.fill[0].label).toBe("Label a");
    expect(review.suggest).toHaveLength(1);
    expect(review.skip).toHaveLength(1);
    expect(review.manual_review).toHaveLength(1);
  });
});

describe("confidenceLevel", () => {
  it("matches the backend thresholds", () => {
    expect(confidenceLevel(0.9)).toBe("High");
    expect(confidenceLevel(0.89)).toBe("Medium");
    expect(confidenceLevel(0.6)).toBe("Medium");
    expect(confidenceLevel(0.59)).toBe("Low");
  });
});

describe("stepState", () => {
  const ready: StepInput = {
    busy: false,
    backendOk: true,
    profileExists: true,
    checkingPage: false,
    pageAllowed: true,
    needsConfirmation: false,
    confirmed: false,
    detected: true,
    analyzed: true,
    fillCount: 3,
  };

  it("enables every step when everything is ready", () => {
    expect(stepState(ready)).toEqual({
      canDetect: true,
      canAnalyze: true,
      canApply: true,
      blocker: null,
    });
  });

  it("blocks everything on an unsupported page", () => {
    const state = stepState({ ...ready, pageAllowed: false });
    expect(state.canDetect || state.canAnalyze || state.canApply).toBe(false);
    expect(state.blocker).toMatch(/not supported/);
  });

  it("requires the real-page confirmation before anything runs", () => {
    const state = stepState({ ...ready, needsConfirmation: true, confirmed: false });
    expect(state.canDetect || state.canAnalyze || state.canApply).toBe(false);
    expect(state.blocker).toMatch(/confirmation/);
    expect(stepState({ ...ready, needsConfirmation: true, confirmed: true }).canApply).toBe(true);
  });

  it("cannot apply before analysis or with nothing to fill", () => {
    expect(stepState({ ...ready, analyzed: false }).canApply).toBe(false);
    expect(stepState({ ...ready, fillCount: 0 }).canApply).toBe(false);
  });

  it("disables every step while busy", () => {
    const state = stepState({ ...ready, busy: true });
    expect(state.canDetect || state.canAnalyze || state.canApply).toBe(false);
  });
});
