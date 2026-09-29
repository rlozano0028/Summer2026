/**
 * Types mirroring the Phase 6 backend extension API.
 *
 * These are hand-written on purpose: the surface is small, and generating types
 * from the OpenAPI schema would add a build dependency for little benefit at
 * this stage. Keep them in sync with backend/app/models/extension.py.
 */

export type FieldAction = "fill" | "suggest" | "manual_review" | "skip";

/** Metadata for one detected field. Never carries the element's value. */
export interface ExtensionDetectedField {
  field_id: string;
  selector: string;
  tag_name: string;
  input_type: string | null;
  name: string | null;
  id_attribute: string | null;
  placeholder: string | null;
  aria_label: string | null;
  label_text: string | null;
  nearby_text: string | null;
  autocomplete: string | null;
  required: boolean;
  visible: boolean;
  disabled: boolean;
  readonly: boolean;
  options: string[];
  is_file_upload: boolean;
  is_submit_control: boolean;
  is_textarea: boolean;
  is_select: boolean;
  is_checkbox: boolean;
  is_radio: boolean;
  /**
   * Phase 7: true for controls the extension will not write to - ARIA comboboxes,
   * contenteditable regions, framework-owned dropdowns. The backend routes these to
   * manual review.
   */
  is_custom_control?: boolean;
  /** Short, non-identifying explanation shown next to a custom control. */
  unsupported_reason?: string | null;
}

export interface ExtensionAnalyzeRequest {
  page_url: string;
  page_title: string | null;
  form_name: string | null;
  fields: ExtensionDetectedField[];
}

/** One piece of evidence behind a mapping decision (Phase 5). */
export interface MatchEvidence {
  source: string;
  matched_text: string;
  matched_rule: string;
  weight: number;
}

/** A mapping decision, with a redacted preview only. */
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
  category: string;
  evidence: MatchEvidence[];
  warnings: string[];
  field_fingerprint: string;
  /** Visible label of the field, when the backend provides it. */
  field_label?: string;
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

/**
 * A transient instruction for the content script.
 *
 * `value` is populated only for a safe `action === "fill"` field. Never persist
 * this object (no chrome.storage, no logging of `value`).
 */
export interface ExtensionFillInstruction {
  field_id: string;
  selector: string;
  action: FieldAction;
  value: string | null;
  value_preview: string | null;
  field_type: string | null;
  category: string | null;
  reason: string;
}

export interface ExtensionAnalyzeResponse {
  page_url: string;
  page_title: string | null;
  profile_review_status: boolean | null;
  warnings: string[];
  fill_plan: FillPlan;
  instructions: ExtensionFillInstruction[];
}

export interface ExtensionHealthResponse {
  ok: boolean;
  backend: string;
  profile_exists: boolean;
  profile_needs_review: boolean | null;
  message: string;
}

/** What safeFiller reports back to the popup after applying instructions. */
export interface ApplyFillResult {
  filled: number;
  failed: number;
  skipped: number;
  warnings: string[];
}

/** What the content script returns for a DETECT_FIELDS message. */
export interface DetectFieldsResult {
  page_url: string;
  page_title: string;
  fields: ExtensionDetectedField[];
  warnings: string[];
  /** Phase 7: which adapter read the page, so the popup can name it. */
  platform_id?: string;
  platform_display_name?: string;
  platform_confidence?: number;
}

/**
 * Envelope for every popup -> content script message.
 *
 * Deliberately loose: the runtime handler has to accept whatever arrives over
 * `chrome.runtime.onMessage`.
 */
export interface ContentMessage {
  type: string;
  instructions?: ExtensionFillInstruction[];
  mappings?: FieldMapping[];
}

/** Uniform reply envelope so the popup can surface content-script errors. */
export type ContentResponse<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };
