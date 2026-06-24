import { useEffect, useState } from "react";
import {
  analyzeSampleForm,
  dryRunSampleForm,
  getSampleForms,
} from "../api/client";
import type { AutofillResult, FillPlan } from "../types/automation";
import { FieldMappingReview } from "./FieldMappingReview";
import { MappingOverrideEditor } from "./MappingOverrideEditor";

// Phase 5 automation panel. Works against local sample forms only.
export function AutomationPrototype() {
  const [forms, setForms] = useState<string[]>([]);
  const [selectedForm, setSelectedForm] = useState<string>("");
  const [plan, setPlan] = useState<FillPlan | null>(null);
  const [dryRunResult, setDryRunResult] = useState<AutofillResult | null>(null);
  const [busy, setBusy] = useState(false);
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
      setError(err instanceof Error ? err.message : "Failed to load sample forms.");
    }
  }

  async function handleAnalyze() {
    if (!selectedForm) return;
    setBusy(true);
    setError(null);
    setDryRunResult(null);
    try {
      setPlan(await analyzeSampleForm(selectedForm));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analyze failed.");
      setPlan(null);
    } finally {
      setBusy(false);
    }
  }

  async function handleDryRun() {
    if (!selectedForm) return;
    setBusy(true);
    setError(null);
    try {
      setDryRunResult(await dryRunSampleForm(selectedForm));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dry run failed.");
      setDryRunResult(null);
    } finally {
      setBusy(false);
    }
  }

  const sensitiveCount =
    plan?.mappings?.filter((m) => m.sensitive).length ?? 0;

  return (
    <section className="card">
      <h2>Field-mapping review (Phase 5)</h2>
      <p className="muted">
        This prototype only analyzes <strong>local sample forms</strong> shipped
        with the app. It does not support real job sites, never submits, and
        always leaves sensitive/legal fields for manual review.
      </p>

      <div className="field-row">
        <label htmlFor="sample-form">Sample form</label>
        <select
          id="sample-form"
          value={selectedForm}
          onChange={(e) => setSelectedForm(e.target.value)}
          disabled={busy || forms.length === 0}
        >
          {forms.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>

      <div className="button-row">
        <button type="button" onClick={() => void handleAnalyze()} disabled={busy || !selectedForm}>
          Analyze form
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => void handleDryRun()}
          disabled={busy || !selectedForm}
        >
          Run dry run
        </button>
      </div>

      {error && <div className="toast toast-error">{error}</div>}

      {plan && (
        <div className="automation-results">
          {sensitiveCount > 0 && (
            <div className="toast toast-error">
              {sensitiveCount} sensitive/legal field(s) detected - all left for
              manual review and never autofilled.
            </div>
          )}
          <FieldMappingReview plan={plan} />
          <MappingOverrideEditor
            plan={plan}
            formName={selectedForm}
            onSaved={() => void handleAnalyze()}
          />
        </div>
      )}

      {dryRunResult && (
        <div className="automation-results">
          <h3>Dry run result</h3>
          <p className="muted">Nothing was typed into the form (dry run).</p>
          <div className="counts">
            <span className="pill pill-fill">
              Would fill: {dryRunResult.filled_fields.length}
            </span>
            <span className="pill pill-suggest">
              Suggested: {dryRunResult.suggested_fields.length}
            </span>
            <span className="pill pill-manual">
              Manual review: {dryRunResult.manual_review_fields.length}
            </span>
            <span className="pill pill-skip">
              Skipped: {dryRunResult.skipped_fields.length}
            </span>
          </div>
          {dryRunResult.report_path && (
            <p className="muted">Redacted report: {dryRunResult.report_path}</p>
          )}
        </div>
      )}

      <p className="muted automation-warning">
        Reminder: real job sites are intentionally not supported in this phase.
      </p>
    </section>
  );
}
