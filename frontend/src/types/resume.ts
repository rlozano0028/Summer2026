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

export interface HealthResponse {
  status: string;
}
