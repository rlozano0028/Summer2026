import { useEffect, useState } from "react";
import {
  analyzeSampleForm,
  dryRunSampleForm,
  getSampleForms,
} from "../api/client";
import type { AutofillResult, FillPlan } from "../types/automation";
import { FieldMappingReview } from "./FieldMappingReview";
import { MappingOverrideEditor } from "./MappingOverrideEditor";

// Runs the mapping engine against the local sample forms shipped with the repo.
// Real application pages are handled by the Chrome extension, not here.
export function AutomationPrototype() {
  const [forms, setForms] = useState<string[]>([]);
  const [formsLoaded, setFormsLoaded] = useState(false);
  const [selectedForm, setSelectedForm] = useState<string>("");
  const [plan, setPlan] = useState<FillPlan | null>(null);
  const [dryRunResult, setDryRunResult] = useState<AutofillResult | null>(null);
  const [busy, setBusy] = useState<"analyze" | "dry-run" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadForms();
  }, []);

  async function loadForms() {
    try {
      const names = await getSampleForms();
      setForms(names);
      if (names.length > 0) {
        setSelectedForm((current) => current || names[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the sample forms.");
    } finally {
      setFormsLoaded(true);
    }
  }

  async function handleAnalyze() {
    if (!selectedForm) return;
    setBusy("analyze");
    setError(null);
    setDryRunResult(null);
    try {
      setPlan(await analyzeSampleForm(selectedForm));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
      setPlan(null);
    } finally {
      setBusy(null);
    }
  }

  async function handleDryRun() {
    if (!selectedForm) return;
    setBusy("dry-run");
    setError(null);
    try {
      setDryRunResult(await dryRunSampleForm(selectedForm));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dry run failed.");
      setDryRunResult(null);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="card">
      <header className="card-header">
        <span className="step">4</span>
        <div>
          <h2>Test on a sample form</h2>
          <p className="muted">
            See what the assistant would do on a local practice form before you use
            the Chrome extension on a real application.
          </p>
        </div>
      </header>

      {formsLoaded && forms.length === 0 && !error && (
        <p className="empty-state">No sample forms found in the sample-forms folder.</p>
      )}

      <div className="toolbar">
        <label className="field field-inline">
          <span>Sample form</span>
          <select
            value={selectedForm}
            onChange={(e) => setSelectedForm(e.target.value)}
            disabled={busy !== null || forms.length === 0}
          >
            {forms.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => void handleAnalyze()}
          disabled={busy !== null || !selectedForm}
        >
          {busy === "analyze" ? "Analyzing…" : "Analyze form"}
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => void handleDryRun()}
          disabled={busy !== null || !selectedForm}
          title="Opens the form in a headless browser without typing anything"
        >
          {busy === "dry-run" ? "Running…" : "Dry run"}
        </button>
      </div>

      {error && <p className="notice notice-error">{error}</p>}

      {!plan && !dryRunResult && !error && forms.length > 0 && (
        <p className="empty-state">
          Pick a form and click <strong>Analyze form</strong> to see every field, the
          decision for it, and why.
        </p>
      )}

      {dryRunResult && (
        <div className="result-block">
          <h3>Dry run result</h3>
          <p className="muted">Nothing was typed into the form and nothing was submitted.</p>
          <dl className="stat-row">
            <div className="stat stat-fill">
              <dt>Would fill</dt>
              <dd className="num">{dryRunResult.filled_fields.length}</dd>
            </div>
            <div className="stat stat-suggest">
              <dt>Suggested</dt>
              <dd className="num">{dryRunResult.suggested_fields.length}</dd>
            </div>
            <div className="stat stat-manual_review">
              <dt>Needs review</dt>
              <dd className="num">{dryRunResult.manual_review_fields.length}</dd>
            </div>
            <div className="stat stat-skip">
              <dt>Skipped</dt>
              <dd className="num">{dryRunResult.skipped_fields.length}</dd>
            </div>
          </dl>
          {dryRunResult.report_path && (
            <p className="muted">
              Redacted report saved to <code>{dryRunResult.report_path}</code>
            </p>
          )}
        </div>
      )}

      {plan && (
        <div className="result-block">
          <FieldMappingReview plan={plan} />
          <MappingOverrideEditor
            plan={plan}
            formName={selectedForm}
            onSaved={() => void handleAnalyze()}
          />
        </div>
      )}
    </section>
  );
}
