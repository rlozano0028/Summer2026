import { useState } from "react";
import type { CandidateProfile } from "../types/candidateProfile";

interface ReviewPanelProps {
  profile: CandidateProfile;
  // Latest parse warnings/missing fields, if a parse just happened.
  warnings: string[];
  missingFields: string[];
  onReviewStatusChange: (needsReview: boolean, note?: string) => void;
  busy: boolean;
}

// Shows review status + notes and lets the user toggle "needs review".
export function ReviewPanel({
  profile,
  warnings,
  missingFields,
  onReviewStatusChange,
  busy,
}: ReviewPanelProps) {
  const [note, setNote] = useState("");
  const { metadata } = profile;

  function markReviewed() {
    onReviewStatusChange(false, note.trim() || "Marked reviewed on local dashboard.");
    setNote("");
  }

  function markNeedsReview() {
    onReviewStatusChange(true, note.trim() || "Flagged as needs review on local dashboard.");
    setNote("");
  }

  return (
    <section className="card">
      <header className="card-header">
        <span className="step">3</span>
        <div>
          <h2>
            Review{" "}
            {metadata.needs_review ? (
              <span className="status-badge status-manual_review">Needs review</span>
            ) : (
              <span className="status-badge status-fill">Reviewed</span>
            )}
          </h2>
          <p className="muted">
            {metadata.needs_review
              ? "Check the profile against your resume, then mark it reviewed."
              : "This profile has been checked and is ready to use."}
          </p>
        </div>
      </header>

      {warnings.length > 0 && (
        <div>
          <h4>Latest parse warnings</h4>
          <ul>
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {missingFields.length > 0 && (
        <div>
          <h4>Missing fields</h4>
          <ul className="chips">
            {missingFields.map((m, i) => (
              <li key={i} className="chip">
                {m}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h4>Review notes</h4>
        {metadata.review_notes.length > 0 ? (
          <ul>
            {metadata.review_notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">No notes yet.</p>
        )}
      </div>

      <label className="field">
        <span>Optional note</span>
        <input
          type="text"
          value={note}
          placeholder="e.g. Verified contact info and skills"
          onChange={(e) => setNote(e.target.value)}
        />
      </label>

      <div className="row">
        <button type="button" onClick={markReviewed} disabled={busy}>
          Mark profile reviewed
        </button>
        <button
          type="button"
          className="secondary"
          onClick={markNeedsReview}
          disabled={busy}
        >
          Mark needs review
        </button>
      </div>
      <p className="muted">Changing the status saves immediately.</p>
    </section>
  );
}
