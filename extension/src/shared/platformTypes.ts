/**
 * Types for the Phase 7 platform layer.
 *
 * Mirrors backend/app/models/platform.py. Hand-written for the same reason as
 * types.ts: the surface is small and a codegen step would buy little here.
 *
 * Two distinct notions of "platform" live in this file, and they must not be
 * confused:
 *
 * - `PlatformDetection` / `PageSafetyDecision` come from the backend and decide
 *   whether a page may be analyzed at all.
 * - `PageSignals` and `PlatformAdapter` are local to the content script and only
 *   decide how to *read* the DOM.
 *
 * A page can be confidently detected and still refused.
 */

import type {
  ExtensionDetectedField,
  ExtensionFillInstruction,
  FieldMapping,
  FillPlan,
} from "./types";

export type PlatformId =
  | "local"
  | "generic"
  | "greenhouse"
  | "lever"
  | "ashby"
  | "workday"
  | "smartrecruiters"
  | "unsupported";

export type RiskLevel = "low" | "medium" | "high";

/** Static description of a platform, from GET /platforms/supported. */
export interface SupportedPlatform {
  platform_id: string;
  display_name: string;
  enabled: boolean;
  default_allowed_domains: string[];
  notes: string | null;
  supports_standard_inputs: boolean;
  supports_custom_selects: boolean;
  supports_iframes: boolean;
  risk_level: string;
}

export interface SupportedPlatformsResponse {
  platforms: SupportedPlatform[];
  extra_approved_domains: string[];
}

/** What platform a page appears to be, and the evidence for it. */
export interface PlatformDetection {
  platform_id: string;
  display_name: string;
  confidence: number;
  matched_by: string[];
  page_url: string;
  allowed: boolean;
  reason: string;
  warnings: string[];
}

/** The authoritative answer about whether a page may be analyzed. */
export interface PageSafetyDecision {
  allowed: boolean;
  platform_id: string | null;
  reason: string;
  warnings: string[];
  requires_user_confirmation: boolean;
  blocked_reason: string | null;
}

export interface CheckUrlResponse {
  detection: PlatformDetection;
  safety: PageSafetyDecision;
}

export interface RealPlatformAnalyzeRequest {
  page_url: string;
  page_title: string | null;
  platform_id: string | null;
  platform_confidence: number | null;
  /** Must be true for any non-loopback page. Records the user's confirmation. */
  user_confirmed_real_page: boolean;
  fields: ExtensionDetectedField[];
}

export interface RealPlatformAnalyzeResponse {
  page_url: string;
  page_title: string | null;
  platform: PlatformDetection | null;
  safety: PageSafetyDecision;
  warnings: string[];
  fill_plan: FillPlan;
  instructions: ExtensionFillInstruction[];
  unsupported_count: number;
}

/**
 * Non-identifying observations about the current page's DOM.
 *
 * Deliberately just counts and booleans: no text content, no values, nothing that
 * could carry personal data out of the page.
 */
export interface PageSignals {
  hostname: string;
  pathname: string;
  formCount: number;
  inputCount: number;
  fileInputCount: number;
  iframeCount: number;
  hasPasswordField: boolean;
  /** Selectors that matched, used as detection evidence. */
  matchedSelectors: string[];
  /** True when the page looks like an application form rather than a listing. */
  looksLikeApplicationForm: boolean;
}

/** What the content script reports for a DETECT_PLATFORM message. */
export interface DetectPlatformResult {
  platform_id: PlatformId;
  display_name: string;
  confidence: number;
  matched_by: string[];
  page_url: string;
  signals: PageSignals;
  warnings: string[];
}

/**
 * A platform adapter: DOM-reading help only.
 *
 * An adapter may improve the metadata attached to a field and may warn about parts
 * of a page it cannot handle. An adapter must never map fields to profile values,
 * decide actions, click anything, open a modal, submit a form, reach into an
 * iframe, or pierce a closed shadow root. All mapping stays in the Phase 5 backend
 * engine; all safety stays in the backend policy and in safeFiller.
 */
export interface PlatformAdapter {
  readonly platformId: PlatformId;
  readonly displayName: string;
  /** Selectors and attributes that identify this platform, with a confidence. */
  detectPlatformSignals(doc: Document): { matched: string[]; confidence: number };
  /** Enrich detected fields with platform-specific labels and flags. */
  enhanceDetectedFields(
    fields: ExtensionDetectedField[],
    doc: Document,
  ): ExtensionDetectedField[];
  /** Things about this platform the user should know before reviewing a plan. */
  getUnsupportedWarnings(doc: Document): string[];
  /** Optional per-field normalization applied before mapping. */
  normalizeFieldMetadata?(field: ExtensionDetectedField): ExtensionDetectedField;
}

/** Counts the popup shows above the plan review. */
export interface PlanCounts {
  detected: number;
  fill: number;
  suggest: number;
  manualReview: number;
  skip: number;
  unsupported: number;
}

export function countPlan(plan: FillPlan, unsupported = 0): PlanCounts {
  const mappings: FieldMapping[] = plan.mappings ?? [];
  return {
    detected: mappings.length,
    fill: plan.fill_count,
    suggest: plan.suggest_count,
    manualReview: plan.manual_review_count,
    skip: plan.skip_count,
    unsupported,
  };
}
