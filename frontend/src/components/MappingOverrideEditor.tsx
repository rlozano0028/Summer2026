import { useMemo, useState } from "react";
import { saveMappingOverride } from "../api/client";
import type { FieldAction, FieldMapping, FillPlan } from "../types/automation";
import { SAFE_CATEGORIES } from "../types/fieldMapping";

// Actions a user may pick. "fill" is only meaningful for a non-sensitive
// category that resolves to a value; the backend enforces that too.
const OVERRIDE_ACTIONS: FieldAction[] = [
  "suggest",
  "manual_review",
  "skip",
  "fill",
];

function fieldLabel(mapping: FieldMapping): string {
  return mapping.profile_path ?? mapping.category ?? mapping.selector;
}

// Phase 5: a simple editor to save a local mapping override for one field.
export function MappingOverrideEditor({
  plan,
  formName,
  onSaved,
}: {
  plan: FillPlan;
  formName: string;
  onSaved?: () => void;
}) {
  const [fieldId, setFieldId] = useState<string>("");
  const [category, setCategory] = useState<string>(SAFE_CATEGORIES[0]);
  const [action, setAction] = useState<FieldAction>("suggest");
  const [note, setNote] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedMapping = useMemo(
    () => plan.mappings.find((m) => m.field_id === fieldId) ?? null,
    [plan.mappings, fieldId],
  );

  async function handleSave() {
    if (!selectedMapping) {
      setError("Select a detected field first.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await saveMappingOverride({
        form_name: formName,
        field_fingerprint: selectedMapping.field_fingerprint,
        category,
        profile_path: null,
        action,
        note: note || null,
      });
      const saveWarnings = result.warnings ?? [];
      const warned = saveWarnings.length
        ? ` (${saveWarnings.join("; ")})`
        : "";
      setMessage(`Saved override as "${result.override.action}".${warned}`);
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save override.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="override-editor">
      <h4>Add a local mapping override</h4>
      <p className="muted">
        Overrides are <strong>local-only</strong> and reused on future runs.
        Sensitive / legal fields can never be forced to autofill - those are
        always saved as manual review.
      </p>

      <div className="field-row">
        <label htmlFor="override-field">Detected field</label>
        <select
          id="override-field"
          value={fieldId}
          onChange={(e) => setFieldId(e.target.value)}
          disabled={busy}
        >
          <option value="">Select a field...</option>
          {plan.mappings.map((m) => (
            <option key={m.field_id} value={m.field_id}>
              {fieldLabel(m)} [{m.category}]
            </option>
          ))}
        </select>
      </div>

      <div className="field-row">
        <label htmlFor="override-category">Category / profile path</label>
        <select
          id="override-category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          disabled={busy}
        >
          {SAFE_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <div className="field-row">
        <label htmlFor="override-action">Action</label>
        <select
          id="override-action"
          value={action}
          onChange={(e) => setAction(e.target.value as FieldAction)}
          disabled={busy}
        >
          {OVERRIDE_ACTIONS.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>

      <div className="field-row">
        <label htmlFor="override-note">Note (optional)</label>
        <input
          id="override-note"
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          disabled={busy}
        />
      </div>

      <button type="button" onClick={() => void handleSave()} disabled={busy || !fieldId}>
        Save override
      </button>

      {message && <div className="toast">{message}</div>}
      {error && <div className="toast toast-error">{error}</div>}
    </div>
  );
}
