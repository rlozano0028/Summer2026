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
      <h2>Review</h2>

      <div className="review-status">
        Status:{" "}
        {metadata.needs_review ? (
          <span className="badge badge-review">Needs review</span>
        ) : (
          <span className="badge badge-ok">Reviewed</span>
        )}
      </div>

      <p className="warning-strong">
        Always manually verify sensitive/legal fields (work authorization,
        sponsorship, salary, demographic, veteran, disability, and criminal-history
        questions). These are never auto-answered.
      </p>

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
          <p className="muted">No review notes yet.</p>
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
      <p className="muted">
        Changing review status saves immediately to the local profile.
      </p>
    </section>
  );
}
