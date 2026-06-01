// TypeScript mirrors of the backend resume-ingestion models.

import type { CandidateProfile } from "./candidateProfile";

// Result returned by POST /resume/parse and /resume/parse-and-save.
export interface ResumeParseResult {
  raw_text: string;
  profile: CandidateProfile;
  warnings: string[];
  missing_fields: string[];
  confidence: number;
  source_file_name: string;
  source_file_type: string;
}

// Result returned by POST /resume/extract-text (metadata + preview).
export interface ExtractTextResult {
  file_name: string;
  file_type: string;
  page_count: number | null;
  character_count: number;
  preview: string;
  truncated: boolean;
  warnings: string[];
}

export interface HealthResponse {
  status: string;
}

export interface DeleteProfileResponse {
  deleted: boolean;
  message: string;
}
