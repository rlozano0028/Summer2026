/**
 * The reviewable fill plan (Phase 7 extraction of the Phase 6 review list).
 *
 * Moved out of Popup.tsx unchanged in behaviour so both the local and real-page
 * flows show the same review, and so the plan rendering can be read on its own.
 *
 * Rows are grouped by action, fill first, because that is the group the user must
 * scrutinise before clicking Apply. Custom controls are shown as "Not supported" -
 * a different statement from "manual review", since the extension could not act on
 * them even if asked.
 *
 * A custom control replaces the action badge rather than sitting beside it. The
 * real-page endpoint already downgrades these to manual review, but the unchanged
 * Phase 6 local endpoint does not, so a loopback fixture can return `fill` for a
 * control the filler will always refuse. Showing "Fill" there would promise
 * something that cannot happen, so the row states the truth instead.
 *
 * Privacy: rows show the backend's redacted `value_preview` only. The real values
 * live in the transient instruction list and are never rendered.
 */

import {
  ACTION_FILL,
  ACTION_LABELS,
  ACTION_MANUAL_REVIEW,
  ACTION_SKIP,
  ACTION_SUGGEST,
} from "../../shared/constants";
import type {
  ExtensionDetectedField,
  FieldMapping,
  FillPlan,
} from "../../shared/types";

const ACTION_ORDER = [
  ACTION_FILL,
  ACTION_SUGGEST,
  ACTION_MANUAL_REVIEW,
  ACTION_SKIP,
] as const;

/** Best-effort label, using the same signals the backend classifies on. */
function fieldLabel(
  field: ExtensionDetectedField | undefined,
  fallback: string,
): string {
  if (!field) return fallback;
  return (
    field.label_text ||
    field.aria_label ||
    field.name ||
    field.placeholder ||
    field.id_attribute ||
    fallback
  );
}

const UNSUPPORTED_REASON =
  "Custom control - the extension cannot set this, so it will not be touched. Fill it in yourself.";

function MappingRow({
  mapping,
  label,
  unsupported,
}: {
  mapping: FieldMapping;
  label: string;
  unsupported: boolean;
}) {
  return (
    <div className="row">
      <div className="row-head">
        <span className="row-name" title={label}>
          {label}
        </span>
        <span>
          {mapping.sensitive && <span className="badge sensitive">Sensitive</span>}{" "}
          {unsupported ? (
            <span className="badge unsupported">Not supported</span>
          ) : (
            <span className={`badge ${mapping.action}`}>
              {ACTION_LABELS[mapping.action] ?? mapping.action}
            </span>
          )}
        </span>
      </div>
      <div className="row-meta">
        {mapping.category} &middot; confidence {(mapping.confidence ?? 0).toFixed(2)}
        {mapping.value_preview && (
          <>
            {" "}
            &middot; <span className="preview">{mapping.value_preview}</span>
          </>
        )}
      </div>
      <div className="row-reason">
        {unsupported ? UNSUPPORTED_REASON : mapping.reason}
      </div>
    </div>
  );
}

export interface FillPlanReviewProps {
  plan: FillPlan;
  fields: ExtensionDetectedField[];
}

export function FillPlanReview({ plan, fields }: FillPlanReviewProps) {
  const fieldsById = new Map(fields.map((field) => [field.field_id, field]));
  const grouped = new Map<string, FieldMapping[]>(
    ACTION_ORDER.map((action) => [action, [] as FieldMapping[]]),
  );
  for (const mapping of plan.mappings) {
    (grouped.get(mapping.action) ?? grouped.get(ACTION_MANUAL_REVIEW)!).push(mapping);
  }

  return (
    <section>
      <h2>Fill plan review</h2>
      <div className="review">
        {ACTION_ORDER.flatMap((action) =>
          (grouped.get(action) ?? []).map((mapping) => {
            const field = fieldsById.get(mapping.field_id);
            return (
              <MappingRow
                key={mapping.field_id}
                mapping={mapping}
                label={fieldLabel(field, mapping.field_id)}
                unsupported={field?.is_custom_control === true}
              />
            );
          }),
        )}
      </div>
    </section>
  );
}
