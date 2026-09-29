// TypeScript mirrors of the backend Phase 5 field-mapping models.

export type FieldAction = "fill" | "suggest" | "manual_review" | "skip";

// One piece of evidence supporting a classification decision.
export interface MatchEvidence {
  source: string;
  matched_text: string;
  matched_rule: string;
  weight: number;
}

// A local, user-controlled mapping override.
export interface MappingOverride {
  override_id: string;
  form_name: string;
  field_fingerprint: string;
  category: string;
  profile_path: string | null;
  action: FieldAction;
  note: string | null;
  created_at: string;
  updated_at: string;
}

// Body for creating/updating an override (id + timestamps are server-side).
export interface MappingOverrideCreate {
  override_id?: string | null;
  form_name: string;
  field_fingerprint: string;
  category: string;
  profile_path?: string | null;
  action: FieldAction;
  note?: string | null;
}

export interface SaveOverrideResponse {
  override: MappingOverride;
  warnings: string[];
}

// Safe, non-sensitive categories a user may pick in the override editor.
export const SAFE_CATEGORIES: readonly string[] = [
  "identity.first_name",
  "identity.last_name",
  "identity.full_name",
  "identity.email",
  "identity.phone",
  "identity.city",
  "identity.state",
  "identity.country",
  "links.linkedin",
  "links.github",
  "links.portfolio",
  "skills.programming_languages",
  "skills.frameworks",
  "skills.tools",
  "skills.databases",
  "skills.cloud",
  "skills.combined",
  "education.school",
  "education.degree",
  "education.major",
  "experience.company",
  "experience.title",
];
