// TypeScript mirrors of the backend Pydantic candidate-profile models.
// Kept intentionally close to backend/app/models/candidate_profile.py for
// Phase 3. Unknown scalar fields are null; unknown collections are empty arrays.

export interface Identity {
  first_name: string | null;
  last_name: string | null;
  full_name: string | null;
  email: string | null;
  phone: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
}

export interface Links {
  linkedin: string | null;
  github: string | null;
  portfolio: string | null;
  other_links: string[];
}

export interface EducationItem {
  school: string | null;
  degree: string | null;
  major: string | null;
  minor: string | null;
  start_month: number | null;
  start_year: number | null;
  end_month: number | null;
  end_year: number | null;
  gpa: number | null;
  location: string | null;
  honors: string[];
  coursework: string[];
}

export interface ExperienceItem {
  company: string | null;
  title: string | null;
  location: string | null;
  start_month: number | null;
  start_year: number | null;
  end_month: number | null;
  end_year: number | null;
  current: boolean | null;
  bullets: string[];
  technologies: string[];
}

export interface ProjectItem {
  name: string | null;
  description: string | null;
  bullets: string[];
  technologies: string[];
  links: string[];
}

export interface Skills {
  programming_languages: string[];
  frameworks: string[];
  tools: string[];
  databases: string[];
  cloud: string[];
  other: string[];
}

// Sensitive legal fields: null means "unknown", never assume yes/no.
export interface WorkAuthorization {
  authorized_to_work_us: boolean | null;
  requires_sponsorship: boolean | null;
  notes: string | null;
}

export interface Preferences {
  preferred_locations: string[];
  remote_preference: string | null;
  start_date: string | null;
  salary_expectation: string | null;
}

export interface Metadata {
  source_file_name: string | null;
  source_file_type: string | null;
  extracted_at: string | null;
  parser_version: string;
  needs_review: boolean;
  review_notes: string[];
}

export interface CandidateProfile {
  identity: Identity;
  links: Links;
  education: EducationItem[];
  experience: ExperienceItem[];
  projects: ProjectItem[];
  skills: Skills;
  work_authorization: WorkAuthorization;
  preferences: Preferences;
  metadata: Metadata;
}

// A blank profile used when nothing is loaded yet, so the editor always has a
// well-formed object to work with.
export function emptyProfile(): CandidateProfile {
  return {
    identity: {
      first_name: null,
      last_name: null,
      full_name: null,
      email: null,
      phone: null,
      city: null,
      state: null,
      country: null,
    },
    links: { linkedin: null, github: null, portfolio: null, other_links: [] },
    education: [],
    experience: [],
    projects: [],
    skills: {
      programming_languages: [],
      frameworks: [],
      tools: [],
      databases: [],
      cloud: [],
      other: [],
    },
    work_authorization: {
      authorized_to_work_us: null,
      requires_sponsorship: null,
      notes: null,
    },
    preferences: {
      preferred_locations: [],
      remote_preference: null,
      start_date: null,
      salary_expectation: null,
    },
    metadata: {
      source_file_name: null,
      source_file_type: null,
      extracted_at: null,
      parser_version: "unknown",
      needs_review: true,
      review_notes: [],
    },
  };
}
