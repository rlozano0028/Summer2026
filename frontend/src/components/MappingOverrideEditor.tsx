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

const ACTION_NAMES: Record<FieldAction, string> = {
  fill: "Fill",
  suggest: "Suggest",
  manual_review: "Needs review",
  skip: "Skip",
};

function fieldLabel(mapping: FieldMapping): string {
  return mapping.field_label || mapping.profile_path || mapping.selector;
}

// Saves a local mapping override for one field of a sample form.
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
      setMessage(`Saved: ${ACTION_NAMES[result.override.action]}.${warned}`);
      onSaved?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save override.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="override-editor">
      <summary>Correct a decision for this form</summary>
      <p className="muted">
        Overrides are saved locally and reused the next time this form is analyzed.
        Sensitive or legal fields can never be forced to fill; they are saved as
        needs review instead.
      </p>

      <div className="grid-2">
        <label className="field">
          <span>Detected field</span>
          <select value={fieldId} onChange={(e) => setFieldId(e.target.value)} disabled={busy}>
            <option value="">Select a field…</option>
            {plan.mappings.map((m) => (
              <option key={m.field_id} value={m.field_id}>
                {fieldLabel(m)} [{m.category}]
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Map it to</span>
          <select value={category} onChange={(e) => setCategory(e.target.value)} disabled={busy}>
            {SAFE_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Decision</span>
          <select
            value={action}
            onChange={(e) => setAction(e.target.value as FieldAction)}
            disabled={busy}
          >
            {OVERRIDE_ACTIONS.map((a) => (
              <option key={a} value={a}>
                {ACTION_NAMES[a]}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Note (optional)</span>
          <input type="text" value={note} onChange={(e) => setNote(e.target.value)} disabled={busy} />
        </label>
      </div>

      <button type="button" onClick={() => void handleSave()} disabled={busy || !fieldId}>
        {busy ? "Saving…" : "Save override"}
      </button>

      {message && <p className="notice notice-success">{message}</p>}
      {error && <p className="notice notice-error">{error}</p>}
    </details>
  );
}
