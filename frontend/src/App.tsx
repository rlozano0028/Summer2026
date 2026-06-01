import { useEffect, useState } from "react";
import {
  ApiError,
  getProfile,
  saveProfile,
  updateReviewStatus,
} from "./api/client";
import { ProfileEditor } from "./components/ProfileEditor";
import { ProfileSummary } from "./components/ProfileSummary";
import { ResumeUpload } from "./components/ResumeUpload";
import { ReviewPanel } from "./components/ReviewPanel";
import { StatusBanner } from "./components/StatusBanner";
import {
  emptyProfile,
  type CandidateProfile,
} from "./types/candidateProfile";
import type { ResumeParseResult } from "./types/resume";
import "./styles/app.css";

function App() {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  // Bumped whenever a fresh profile is loaded/parsed, to remount the editor.
  const [editorKey, setEditorKey] = useState(0);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [missingFields, setMissingFields] = useState<string[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Try to load any previously saved profile on first render.
  useEffect(() => {
    void loadExistingProfile();
  }, []);

  function applyProfile(next: CandidateProfile) {
    setProfile(next);
    setEditorKey((k) => k + 1);
  }

  async function loadExistingProfile() {
    setError(null);
    try {
      const existing = await getProfile();
      applyProfile(existing);
      setMessage("Loaded saved profile.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        // No saved profile yet - that's fine.
        setMessage(null);
      } else {
        setError(err instanceof Error ? err.message : "Failed to load profile.");
      }
    }
  }

  function handleParsed(result: ResumeParseResult) {
    applyProfile(result.profile);
    setWarnings(result.warnings);
    setMissingFields(result.missing_fields);
    setMessage("Resume parsed and saved. Please review the fields below.");
    setError(null);
  }

  function handleNewProfile() {
    if (
      profile &&
      !window.confirm(
        "Start a new blank profile in the editor? Your saved profile on disk is unchanged until you click Save profile.",
      )
    ) {
      return;
    }
    applyProfile(emptyProfile());
    setWarnings([]);
    setMissingFields([]);
    setMessage(
      "New blank profile — fill in the fields below, then click Save profile.",
    );
    setError(null);
  }

  async function handleSave(updated: CandidateProfile) {
    setBusy(true);
    setError(null);
    try {
      const saved = await saveProfile(updated);
      setProfile(saved);
      setMessage("Profile saved locally.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile.");
    } finally {
      setBusy(false);
    }
  }

  async function handleReviewStatusChange(needsReview: boolean, note?: string) {
    setBusy(true);
    setError(null);
    try {
      const saved = await updateReviewStatus(needsReview, note);
      setProfile(saved);
      setMessage(
        needsReview ? "Marked as needs review." : "Marked as reviewed.",
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("Save a profile before changing review status.");
      } else {
        setError(err instanceof Error ? err.message : "Failed to update status.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-row">
          <div>
            <h1>Resume Autofill Assistant — Local Dashboard</h1>
            <p className="muted">
              Upload a resume, start from scratch, review, and save locally. Nothing
              leaves your machine.
            </p>
          </div>
          <button
            type="button"
            className="secondary"
            onClick={handleNewProfile}
            disabled={busy}
          >
            New profile
          </button>
        </div>
      </header>

      <StatusBanner />

      {message && <div className="toast toast-info">{message}</div>}
      {error && <div className="toast toast-error">{error}</div>}

      <main className="layout">
        <div className="column">
          <ResumeUpload onParsed={handleParsed} />
          {profile ? (
            <ProfileEditor
              key={editorKey}
              profile={profile}
              onSave={handleSave}
              busy={busy}
            />
          ) : (
            <section className="card">
              <h2>2. Edit profile</h2>
              <p className="muted">
                No profile loaded yet. Click <strong>New profile</strong> above to
                write one from scratch, or upload a resume.
              </p>
            </section>
          )}
        </div>

        <div className="column">
          {profile && <ProfileSummary profile={profile} />}
          {profile && (
            <ReviewPanel
              profile={profile}
              warnings={warnings}
              missingFields={missingFields}
              onReviewStatusChange={handleReviewStatusChange}
              busy={busy}
            />
          )}
        </div>
      </main>

      <footer className="app-footer muted">
        Local-first · resume files are never stored · only the reviewed profile JSON
        is saved
      </footer>
    </div>
  );
}

export default App;
