import { useMemo, useState } from "react";
import type {
  CandidateProfile,
  EducationItem,
  ExperienceItem,
  ProjectItem,
} from "../types/candidateProfile";

interface ProfileEditorProps {
  profile: CandidateProfile;
  onSave: (profile: CandidateProfile) => void;
  busy: boolean;
}

// --- small helpers --------------------------------------------------------

function listToText(values: string[]): string {
  return values.join(", ");
}

function textToList(text: string): string[] {
  return text
    .split(",")
    .map((v) => v.trim())
    .filter((v) => v.length > 0);
}

function orNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

// Tri-state mapping for sensitive boolean fields (unknown / yes / no).
function boolToSelect(value: boolean | null): string {
  if (value === true) return "true";
  if (value === false) return "false";
  return "";
}

function selectToBool(value: string): boolean | null {
  if (value === "true") return true;
  if (value === "false") return false;
  return null;
}

export function ProfileEditor({ profile, onSave, busy }: ProfileEditorProps) {
  const { identity, links, skills, work_authorization, preferences } = profile;

  // Scalar string fields.
  const [fullName, setFullName] = useState(identity.full_name ?? "");
  const [firstName, setFirstName] = useState(identity.first_name ?? "");
  const [lastName, setLastName] = useState(identity.last_name ?? "");
  const [email, setEmail] = useState(identity.email ?? "");
  const [phone, setPhone] = useState(identity.phone ?? "");
  const [city, setCity] = useState(identity.city ?? "");
  const [stateRegion, setStateRegion] = useState(identity.state ?? "");
  const [country, setCountry] = useState(identity.country ?? "");

  const [linkedin, setLinkedin] = useState(links.linkedin ?? "");
  const [github, setGithub] = useState(links.github ?? "");
  const [portfolio, setPortfolio] = useState(links.portfolio ?? "");

  // Skill lists as comma-separated text.
  const [langs, setLangs] = useState(listToText(skills.programming_languages));
  const [frameworks, setFrameworks] = useState(listToText(skills.frameworks));
  const [tools, setTools] = useState(listToText(skills.tools));
  const [databases, setDatabases] = useState(listToText(skills.databases));
  const [cloud, setCloud] = useState(listToText(skills.cloud));
  const [otherSkills, setOtherSkills] = useState(listToText(skills.other));

  // Sensitive work authorization fields (tri-state).
  const [authorized, setAuthorized] = useState(
    boolToSelect(work_authorization.authorized_to_work_us),
  );
  const [sponsorship, setSponsorship] = useState(
    boolToSelect(work_authorization.requires_sponsorship),
  );
  const [authNotes, setAuthNotes] = useState(work_authorization.notes ?? "");

  // Preferences.
  const [preferredLocations, setPreferredLocations] = useState(
    listToText(preferences.preferred_locations),
  );
  const [remotePref, setRemotePref] = useState(preferences.remote_preference ?? "");
  const [startDate, setStartDate] = useState(preferences.start_date ?? "");
  const [salary, setSalary] = useState(preferences.salary_expectation ?? "");

  // Complex nested arrays edited as JSON text in Phase 3.
  const [educationJson, setEducationJson] = useState(
    JSON.stringify(profile.education, null, 2),
  );
  const [experienceJson, setExperienceJson] = useState(
    JSON.stringify(profile.experience, null, 2),
  );
  const [projectsJson, setProjectsJson] = useState(
    JSON.stringify(profile.projects, null, 2),
  );

  const [jsonError, setJsonError] = useState<string | null>(null);

  // Preserve other_links since the editor doesn't expose it directly.
  const otherLinks = useMemo(() => links.other_links, [links.other_links]);

  function handleSave() {
    setJsonError(null);

    let education: EducationItem[];
    let experience: ExperienceItem[];
    let projects: ProjectItem[];
    try {
      education = parseJsonArray<EducationItem>(educationJson, "Education");
      experience = parseJsonArray<ExperienceItem>(experienceJson, "Experience");
      projects = parseJsonArray<ProjectItem>(projectsJson, "Projects");
    } catch (err) {
      setJsonError(err instanceof Error ? err.message : "Invalid JSON.");
      return;
    }

    const updated: CandidateProfile = {
      ...profile,
      identity: {
        first_name: orNull(firstName),
        last_name: orNull(lastName),
        full_name: orNull(fullName),
        email: orNull(email),
        phone: orNull(phone),
        city: orNull(city),
        state: orNull(stateRegion),
        country: orNull(country),
      },
      links: {
        linkedin: orNull(linkedin),
        github: orNull(github),
        portfolio: orNull(portfolio),
        other_links: otherLinks,
      },
      skills: {
        programming_languages: textToList(langs),
        frameworks: textToList(frameworks),
        tools: textToList(tools),
        databases: textToList(databases),
        cloud: textToList(cloud),
        other: textToList(otherSkills),
      },
      work_authorization: {
        authorized_to_work_us: selectToBool(authorized),
        requires_sponsorship: selectToBool(sponsorship),
        notes: orNull(authNotes),
      },
      preferences: {
        preferred_locations: textToList(preferredLocations),
        remote_preference: orNull(remotePref),
        start_date: orNull(startDate),
        salary_expectation: orNull(salary),
      },
      education,
      experience,
      projects,
      // Metadata (incl. review status) is preserved; editing does not auto-review.
      metadata: profile.metadata,
    };

    onSave(updated);
  }

  return (
    <section className="card">
      <header className="card-header">
        <span className="step">2</span>
        <div>
          <h2>Edit profile</h2>
          <p className="muted">
            Correct anything the parser got wrong. Saving stores the profile locally;
            mark it reviewed in step 3 when you are done.
          </p>
        </div>
      </header>

      <h3>Identity</h3>
      <div className="grid-2">
        <TextField label="Full name" value={fullName} onChange={setFullName} />
        <TextField label="Email" type="email" value={email} onChange={setEmail} />
        <TextField label="First name" value={firstName} onChange={setFirstName} />
        <TextField label="Last name" value={lastName} onChange={setLastName} />
        <TextField label="Phone" type="tel" value={phone} onChange={setPhone} />
        <TextField label="City" value={city} onChange={setCity} />
        <TextField label="State" value={stateRegion} onChange={setStateRegion} />
        <TextField label="Country" value={country} onChange={setCountry} />
      </div>

      <h3>Links</h3>
      <div className="grid-2">
        <TextField label="LinkedIn" type="url" value={linkedin} onChange={setLinkedin} />
        <TextField label="GitHub" type="url" value={github} onChange={setGithub} />
        <TextField label="Portfolio" type="url" value={portfolio} onChange={setPortfolio} />
      </div>

      <h3>Skills (comma-separated)</h3>
      <div className="grid-2">
        <TextField label="Programming languages" value={langs} onChange={setLangs} />
        <TextField label="Frameworks" value={frameworks} onChange={setFrameworks} />
        <TextField label="Tools" value={tools} onChange={setTools} />
        <TextField label="Databases" value={databases} onChange={setDatabases} />
        <TextField label="Cloud" value={cloud} onChange={setCloud} />
        <TextField label="Other skills" value={otherSkills} onChange={setOtherSkills} />
      </div>

      <h3>
        Work authorization <span className="status-badge status-protected">Protected</span>
      </h3>
      <p className="notice notice-protected">
        Kept for your reference only. These answers are never filled into an
        application; you answer them yourself on each form.
      </p>
      <div className="grid-2">
        <SelectField
          label="Authorized to work (US)"
          value={authorized}
          onChange={setAuthorized}
        />
        <SelectField
          label="Requires sponsorship"
          value={sponsorship}
          onChange={setSponsorship}
        />
      </div>
      <TextField label="Authorization notes" value={authNotes} onChange={setAuthNotes} />

      <h3>Preferences</h3>
      <div className="grid-2">
        <TextField
          label="Preferred locations (comma-separated)"
          value={preferredLocations}
          onChange={setPreferredLocations}
        />
        <TextField label="Remote preference" value={remotePref} onChange={setRemotePref} />
        <TextField label="Start date" value={startDate} onChange={setStartDate} />
        <TextField
          label="Salary expectation (never auto-filled)"
          value={salary}
          onChange={setSalary}
        />
      </div>

      <h3>Education / Experience / Projects (JSON)</h3>
      <p className="muted">
        Edit these as JSON arrays. Invalid JSON will not be saved.
      </p>
      <JsonField label="Education" value={educationJson} onChange={setEducationJson} />
      <JsonField label="Experience" value={experienceJson} onChange={setExperienceJson} />
      <JsonField label="Projects" value={projectsJson} onChange={setProjectsJson} />

      {jsonError && <p className="notice notice-error">{jsonError}</p>}

      <div className="row">
        <button type="button" onClick={handleSave} disabled={busy}>
          {busy ? "Saving…" : "Save profile"}
        </button>
      </div>
    </section>
  );
}

// Parse a JSON string that must be an array; throws a friendly error otherwise.
function parseJsonArray<T>(text: string, label: string): T[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    const message = err instanceof Error ? err.message : "syntax error";
    throw new Error(`${label}: invalid JSON (${message}).`);
  }
  if (!Array.isArray(parsed)) {
    throw new Error(`${label}: expected a JSON array (e.g. []).`);
  }
  return parsed as T[];
}

// --- field primitives -----------------------------------------------------

function TextField({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: "text" | "email" | "tel" | "url";
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function SelectField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Unknown</option>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    </label>
  );
}

function JsonField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <textarea
        className="json-area"
        rows={6}
        value={value}
        spellCheck={false}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
