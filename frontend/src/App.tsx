import { useEffect, useState } from "react";
import {
  ApiError,
  getProfile,
  saveProfile,
  updateReviewStatus,
} from "./api/client";
import { AutomationPrototype } from "./components/AutomationPrototype";
import { ProfileEditor } from "./components/ProfileEditor";
import { ProfileSummary } from "./components/ProfileSummary";
import { ResumeUpload } from "./components/ResumeUpload";
import { ReviewPanel } from "./components/ReviewPanel";
import { OfflineBanner, useBackendHealth } from "./components/StatusBanner";
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
  const [confirmingNew, setConfirmingNew] = useState(false);
  const [backend, recheckBackend] = useBackendHealth();

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
      setMessage(null);
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
    setMessage("Resume parsed and saved. Review every field below before using it.");
    setError(null);
  }

  function handleNewProfile() {
    // Replacing a loaded profile in the editor needs a second click.
    if (profile && !confirmingNew) {
      setConfirmingNew(true);
      return;
    }
    setConfirmingNew(false);
    applyProfile(emptyProfile());
    setWarnings([]);
    setMissingFields([]);
    setMessage("New blank profile. Fill in the fields, then click Save profile.");
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
        needsReview ? "Profile marked as needs review." : "Profile marked as reviewed.",
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

  const profileState = !profile
    ? { label: "No profile", tone: "skip" }
    : profile.metadata.needs_review
      ? { label: "Needs review", tone: "manual_review" }
      : { label: "Reviewed", tone: "fill" };
  const backendState = {
    checking: { label: "Checking…", tone: "skip" },
    online: { label: "Connected", tone: "fill" },
    offline: { label: "Offline", tone: "danger" },
  }[backend];

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <h1>Autofill Assistant</h1>
          <p className="muted">Local dashboard for your application profile</p>
        </div>
        <dl className="status-chips">
          <div className="status-chip">
            <dt>Backend</dt>
            <dd>
              <span className={`status-dot status-${backendState.tone}`} aria-hidden="true" />
              {backendState.label}
            </dd>
          </div>
          <div className="status-chip">
            <dt>Profile</dt>
            <dd>
              <span className={`status-dot status-${profileState.tone}`} aria-hidden="true" />
              {profileState.label}
            </dd>
          </div>
        </dl>
        <div className="header-actions">
          {confirmingNew ? (
            <>
              <span className="muted">Discard unsaved edits?</span>
              <button type="button" className="danger" onClick={handleNewProfile}>
                Start blank
              </button>
              <button type="button" className="secondary" onClick={() => setConfirmingNew(false)}>
                Cancel
              </button>
            </>
          ) : (
            <button type="button" className="secondary" onClick={handleNewProfile} disabled={busy}>
              New profile
            </button>
          )}
        </div>
      </header>

      <ul className="safety-strip" aria-label="Safety rules">
        <li>
          <strong>You submit.</strong> Nothing is ever submitted for you.
        </li>
        <li>
          <strong>Sensitive questions are protected.</strong> Work authorization,
          sponsorship, salary, EEO, and legal questions are never filled.
        </li>
        <li>
          <strong>Local only.</strong> Your profile stays on this computer.
        </li>
      </ul>

      {backend === "offline" && <OfflineBanner onRetry={recheckBackend} />}

      {message && (
        <p className="notice notice-success" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="notice notice-error" role="alert">
          {error}
        </p>
      )}

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
              <header className="card-header">
                <span className="step">2</span>
                <h2>Edit profile</h2>
              </header>
              <p className="empty-state">
                No profile yet. Upload a resume above, or click{" "}
                <strong>New profile</strong> to write one from scratch.
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

        <div className="span-all">
          <AutomationPrototype />
        </div>
      </main>

      <footer className="app-footer muted">
        Resume files are parsed in memory and never stored. Only the profile you
        review is saved, to <code>backend/app/data/profile.json</code>.
      </footer>
    </div>
  );
}

export default App;
