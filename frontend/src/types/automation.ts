// TypeScript mirrors of the backend automation models (Phase 4 + Phase 5).

import type { FieldAction, MatchEvidence } from "./fieldMapping";

export type { FieldAction } from "./fieldMapping";

export interface FieldMapping {
  field_id: string;
  selector: string;
  profile_path: string | null;
  value_preview: string | null;
  confidence: number;
  action: FieldAction;
  reason: string;
  sensitive: boolean;
  missing_value: boolean;
  // Phase 5 additions.
  category: string;
  evidence: MatchEvidence[];
  warnings: string[];
  field_fingerprint: string;
  field_label: string;
}

export interface FillPlan {
  form_name: string;
  form_url: string;
  generated_at: string;
  mappings: FieldMapping[];
  warnings: string[];
  manual_review_count: number;
  fill_count: number;
  suggest_count: number;
  skip_count: number;
}

export interface AutofillResult {
  form_name: string;
  form_url: string;
  started_at: string;
  completed_at: string | null;
  filled_fields: string[];
  suggested_fields: string[];
  manual_review_fields: string[];
  skipped_fields: string[];
  warnings: string[];
  report_path: string | null;
  success: boolean;
  plan: FillPlan | null;
}

export interface SampleFormsResponse {
  forms: string[];
}

const KNOWN_ACTIONS: FieldAction[] = ["fill", "suggest", "manual_review", "skip"];

function asFieldAction(value: unknown): FieldAction {
  if (typeof value === "string" && KNOWN_ACTIONS.includes(value as FieldAction)) {
    return value as FieldAction;
  }
  return "manual_review";
}

/** Ensure Phase 5 list fields exist so render never crashes on partial API data. */
export function normalizeFieldMapping(raw: Partial<FieldMapping> & Pick<FieldMapping, "field_id" | "selector">): FieldMapping {
  return {
    field_id: raw.field_id,
    selector: raw.selector,
    profile_path: raw.profile_path ?? null,
    value_preview: raw.value_preview ?? null,
    confidence: typeof raw.confidence === "number" ? raw.confidence : 0,
    action: asFieldAction(raw.action),
    reason: raw.reason ?? "",
    sensitive: Boolean(raw.sensitive),
    missing_value: Boolean(raw.missing_value),
    category: raw.category ?? "unknown",
    evidence: Array.isArray(raw.evidence) ? raw.evidence : [],
    warnings: Array.isArray(raw.warnings) ? raw.warnings : [],
    field_fingerprint: raw.field_fingerprint ?? "",
    field_label: raw.field_label ?? "",
  };
}

export function normalizeFillPlan(raw: Partial<FillPlan> & Pick<FillPlan, "form_name" | "form_url" | "generated_at">): FillPlan {
  const mappings = Array.isArray(raw.mappings)
    ? raw.mappings.map((m) => normalizeFieldMapping(m))
    : [];
  return {
    form_name: raw.form_name,
    form_url: raw.form_url,
    generated_at: raw.generated_at,
    mappings,
    warnings: Array.isArray(raw.warnings) ? raw.warnings : [],
    manual_review_count: raw.manual_review_count ?? 0,
    fill_count: raw.fill_count ?? 0,
    suggest_count: raw.suggest_count ?? 0,
    skip_count: raw.skip_count ?? 0,
  };
}
