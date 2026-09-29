/**
 * Pure popup logic: how plan decisions are grouped, and which step buttons are
 * available. Kept out of the React components so it can be unit-tested.
 *
 * The grouping mirrors frontend/src/lib/decisions.ts; keep the two in step.
 */

import type { ExtensionDetectedField, FieldMapping, FillPlan } from "../shared/types";

export type DecisionGroup = "fill" | "suggest" | "manual_review" | "protected" | "skip";

export const GROUP_ORDER: DecisionGroup[] = [
  "fill",
  "suggest",
  "manual_review",
  "protected",
  "skip",
];

export const GROUP_INFO: Record<DecisionGroup, { label: string; hint: string }> = {
  fill: { label: "Will fill", hint: "Plain profile fields matched with high confidence." },
  suggest: { label: "Suggested", hint: "Probable matches. Not filled; check and type them yourself." },
  manual_review: { label: "Needs review", hint: "Low confidence, no profile value, or a control the extension cannot set." },
  protected: { label: "Protected", hint: "Sensitive or legal questions. Never filled." },
  skip: { label: "Skipped", hint: "Buttons, hidden, disabled, or read-only fields." },
};

export interface ReviewRow {
  mapping: FieldMapping;
  group: DecisionGroup;
  label: string;
  /** A custom control the filler refuses to touch, whatever the plan says. */
  unsupported: boolean;
}

function labelFor(mapping: FieldMapping, field: ExtensionDetectedField | undefined): string {
  return (
    field?.label_text ||
    field?.aria_label ||
    mapping.field_label ||
    field?.name ||
    field?.placeholder ||
    field?.id_attribute ||
    mapping.field_id
  );
}

/**
 * Sensitive fields always land in Protected. Custom controls land in Needs review
 * even if the (local) endpoint said fill, because the filler will refuse them and
 * the review must not promise a fill that cannot happen.
 */
export function groupFor(mapping: FieldMapping, unsupported: boolean): DecisionGroup {
  if (mapping.sensitive) return "protected";
  if (unsupported && mapping.action !== "skip") return "manual_review";
  if (GROUP_ORDER.includes(mapping.action as DecisionGroup)) {
    return mapping.action as DecisionGroup;
  }
  return "manual_review";
}

export function buildReview(
  plan: FillPlan,
  fields: ExtensionDetectedField[],
): Record<DecisionGroup, ReviewRow[]> {
  const byId = new Map(fields.map((field) => [field.field_id, field]));
  const groups: Record<DecisionGroup, ReviewRow[]> = {
    fill: [],
    suggest: [],
    manual_review: [],
    protected: [],
    skip: [],
  };
  for (const mapping of plan.mappings ?? []) {
    const field = byId.get(mapping.field_id);
    const unsupported = field?.is_custom_control === true;
    const group = groupFor(mapping, unsupported);
    groups[group].push({ mapping, group, label: labelFor(mapping, field), unsupported });
  }
  return groups;
}

/** Same thresholds as the backend's FILL_THRESHOLD / SUGGEST_THRESHOLD. */
export function confidenceLevel(confidence: number): "High" | "Medium" | "Low" {
  if (confidence >= 0.9) return "High";
  if (confidence >= 0.6) return "Medium";
  return "Low";
}

export interface StepInput {
  busy: boolean;
  backendOk: boolean;
  profileExists: boolean;
  checkingPage: boolean;
  pageAllowed: boolean;
  needsConfirmation: boolean;
  confirmed: boolean;
  detected: boolean;
  analyzed: boolean;
  fillCount: number;
}

export interface StepState {
  canDetect: boolean;
  canAnalyze: boolean;
  canApply: boolean;
  /** Why the next step is unavailable, or null when it is. */
  blocker: string | null;
}

/** Decide which step buttons are enabled, and explain the first thing in the way. */
export function stepState(input: StepInput): StepState {
  const pageReady =
    input.pageAllowed && (!input.needsConfirmation || input.confirmed);
  const canDetect = !input.busy && pageReady;
  const canAnalyze =
    canDetect && input.detected && input.backendOk && input.profileExists;
  const canApply = canAnalyze && input.analyzed && input.fillCount > 0;

  let blocker: string | null = null;
  if (input.checkingPage) blocker = "Checking this page…";
  else if (!input.pageAllowed) blocker = "This page is not supported, so nothing can run here.";
  else if (input.needsConfirmation && !input.confirmed)
    blocker = "Tick the confirmation above to continue.";
  else if (!input.backendOk) blocker = "Start the local backend to build a plan.";
  else if (!input.profileExists) blocker = "Save a profile in the dashboard first.";
  else if (input.analyzed && input.fillCount === 0)
    blocker = "Nothing on this page is safe to fill automatically.";

  return { canDetect, canAnalyze, canApply, blocker };
}
