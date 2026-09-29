// Typed API client for the local backend.
// Base URL defaults to the local FastAPI server and can be overridden with the
// VITE_API_BASE_URL environment variable.

import {
  normalizeFillPlan,
  type AutofillResult,
  type FillPlan,
  type SampleFormsResponse,
} from "../types/automation";
import type {
  MappingOverrideCreate,
  SaveOverrideResponse,
} from "../types/fieldMapping";
import type { CandidateProfile } from "../types/candidateProfile";
import type {
  HealthResponse,
  ResumeParseResult,
} from "../types/resume";

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

// Thrown for any non-2xx response, carrying the HTTP status and a message.
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseError(response: Response): Promise<never> {
  let detail = `${response.status} ${response.statusText}`;
  try {
    const body = await response.json();
    if (body && typeof body.detail === "string") {
      detail = body.detail;
    }
  } catch {
    // Response had no JSON body; keep the status-based message.
  }
  throw new ApiError(response.status, detail);
}

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    return parseError(response);
  }
  return (await response.json()) as T;
}

export async function getHealth(): Promise<HealthResponse> {
  return jsonRequest<HealthResponse>("/health");
}

export async function getProfile(): Promise<CandidateProfile> {
  return jsonRequest<CandidateProfile>("/profile");
}

export async function saveProfile(
  profile: CandidateProfile,
): Promise<CandidateProfile> {
  return jsonRequest<CandidateProfile>("/profile", {
    method: "PUT",
    body: JSON.stringify(profile),
  });
}

export async function updateReviewStatus(
  needsReview: boolean,
  reviewNote?: string,
): Promise<CandidateProfile> {
  return jsonRequest<CandidateProfile>("/profile/review-status", {
    method: "PATCH",
    body: JSON.stringify({
      needs_review: needsReview,
      review_note: reviewNote ?? null,
    }),
  });
}

export async function parseResumeAndSave(
  file: File,
): Promise<ResumeParseResult> {
  // multipart/form-data: let the browser set the Content-Type/boundary.
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/resume/parse-and-save`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    return parseError(response);
  }
  return (await response.json()) as ResumeParseResult;
}

// --- Phase 4: browser automation (local sample forms only) ---

export async function getSampleForms(): Promise<string[]> {
  const data = await jsonRequest<SampleFormsResponse>("/automation/sample-forms");
  return data.forms;
}

export async function analyzeSampleForm(formName: string): Promise<FillPlan> {
  const raw = await jsonRequest<FillPlan>("/automation/analyze", {
    method: "POST",
    body: JSON.stringify({ form_name: formName }),
  });
  return normalizeFillPlan(raw);
}

export async function dryRunSampleForm(
  formName: string,
): Promise<AutofillResult> {
  return jsonRequest<AutofillResult>("/automation/dry-run", {
    method: "POST",
    body: JSON.stringify({ form_name: formName }),
  });
}

// --- Phase 5: local mapping overrides (local-only, user-controlled) ---

export async function saveMappingOverride(
  override: MappingOverrideCreate,
): Promise<SaveOverrideResponse> {
  return jsonRequest<SaveOverrideResponse>("/mapping-overrides", {
    method: "POST",
    body: JSON.stringify(override),
  });
}
