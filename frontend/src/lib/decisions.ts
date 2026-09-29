// How fill-plan decisions are grouped and described in the UI.
// Mirrored in extension/src/popup/decisions.ts; keep the two in step.

import type { FieldMapping, FillPlan } from "../types/automation";

export type DecisionGroup = "fill" | "suggest" | "manual_review" | "skip" | "protected";

export const GROUP_ORDER: DecisionGroup[] = [
  "fill",
  "suggest",
  "manual_review",
  "protected",
  "skip",
];

export const GROUP_INFO: Record<DecisionGroup, { label: string; hint: string }> = {
  fill: {
    label: "Will fill",
    hint: "High-confidence matches to plain profile fields.",
  },
  suggest: {
    label: "Suggested",
    hint: "Probable matches. Check them, then fill by hand if right.",
  },
  manual_review: {
    label: "Needs review",
    hint: "Low confidence or no profile value. You answer these.",
  },
  protected: {
    label: "Protected",
    hint: "Sensitive or legal questions. Never filled automatically.",
  },
  skip: {
    label: "Skipped",
    hint: "Buttons, hidden, disabled, or read-only fields. Left untouched.",
  },
};

// Sensitive fields are always their own group, whatever action the backend chose
// (it is always manual_review or skip for them).
export function groupOf(mapping: FieldMapping): DecisionGroup {
  return mapping.sensitive ? "protected" : mapping.action;
}

export function groupMappings(plan: FillPlan): Record<DecisionGroup, FieldMapping[]> {
  const groups: Record<DecisionGroup, FieldMapping[]> = {
    fill: [],
    suggest: [],
    manual_review: [],
    protected: [],
    skip: [],
  };
  for (const mapping of plan.mappings) {
    (groups[groupOf(mapping)] ?? groups.manual_review).push(mapping);
  }
  return groups;
}

// Same thresholds as backend/app/services/field_mapper.py (FILL / SUGGEST).
export type ConfidenceLevel = "High" | "Medium" | "Low";

export function confidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence >= 0.9) return "High";
  if (confidence >= 0.6) return "Medium";
  return "Low";
}
