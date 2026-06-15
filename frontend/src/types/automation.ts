// TypeScript mirrors of the backend automation models (Phase 4).

export type FieldAction = "fill" | "suggest" | "manual_review" | "skip";

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
}

export interface SampleFormsResponse {
  forms: string[];
}
