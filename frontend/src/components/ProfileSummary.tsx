import type { CandidateProfile } from "../types/candidateProfile";

interface ProfileSummaryProps {
  profile: CandidateProfile;
}

function topSkills(profile: CandidateProfile, limit = 8): string[] {
  const s = profile.skills;
  return [
    ...s.programming_languages,
    ...s.frameworks,
    ...s.databases,
    ...s.tools,
    ...s.cloud,
    ...s.other,
  ].slice(0, limit);
}

// Quick read-only snapshot so the user can see whether parsing worked.
export function ProfileSummary({ profile }: ProfileSummaryProps) {
  const { identity, links, metadata } = profile;
  const skills = topSkills(profile);

  return (
    <section className="card">
      <h2>Profile summary</h2>
      <dl className="summary-grid">
        <dt>Name</dt>
        <dd>{identity.full_name || "—"}</dd>
        <dt>Email</dt>
        <dd>{identity.email || "—"}</dd>
        <dt>Phone</dt>
        <dd>{identity.phone || "—"}</dd>
        <dt>LinkedIn</dt>
        <dd>{links.linkedin || "—"}</dd>
        <dt>GitHub</dt>
        <dd>{links.github || "—"}</dd>
        <dt>Top skills</dt>
        <dd>{skills.length > 0 ? skills.join(", ") : "—"}</dd>
        <dt>Review status</dt>
        <dd>
          {metadata.needs_review ? (
            <span className="badge badge-review">Needs review</span>
          ) : (
            <span className="badge badge-ok">Reviewed</span>
          )}
        </dd>
      </dl>
    </section>
  );
}
