import { useState } from "react";
import type { FieldAction, FieldMapping, FillPlan } from "../types/automation";

const ACTION_LABELS: Record<FieldAction, string> = {
  fill: "Will fill",
  suggest: "Suggestions",
  manual_review: "Needs manual review",
  skip: "Skipped",
};

const GROUP_ORDER: FieldAction[] = ["fill", "suggest", "manual_review", "skip"];

const PILL_CLASS: Record<FieldAction, string> = {
  fill: "pill-fill",
  suggest: "pill-suggest",
  manual_review: "pill-manual",
  skip: "pill-skip",
};

function fieldLabel(mapping: FieldMapping): string {
  return mapping.profile_path ?? mapping.category ?? mapping.selector;
}

function MappingRow({ mapping }: { mapping: FieldMapping }) {
  const [expanded, setExpanded] = useState(false);
  const evidence = mapping.evidence ?? [];
  const warnings = mapping.warnings ?? [];
  const hasEvidence = evidence.length > 0;

  return (
    <li className="mapping-row">
      <div className="mapping-row-main">
        <div className="mapping-row-head">
          <strong>{fieldLabel(mapping)}</strong>
          <span className={`pill ${PILL_CLASS[mapping.action]}`}>
            {mapping.category}
          </span>
          <span className="muted">conf {(mapping.confidence ?? 0).toFixed(2)}</span>
          {mapping.sensitive && (
            <span className="flag flag-sensitive">sensitive</span>
          )}
          {mapping.missing_value && <span className="flag">missing value</span>}
        </div>
        <div className="muted mapping-reason">{mapping.reason}</div>
        {mapping.value_preview && (
          <div className="muted">Preview: {mapping.value_preview}</div>
        )}
        {warnings.map((w, i) => (
          <div key={i} className="toast toast-error mapping-warning">
            {w}
          </div>
        ))}
        {hasEvidence && (
          <button
            type="button"
            className="link-button"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? "Hide evidence" : `Show evidence (${evidence.length})`}
          </button>
        )}
        {expanded && (
          <ul className="evidence-list">
            {evidence.map((ev, i) => (
              <li key={i} className="muted">
                <code>{ev.source}</code> matched "{ev.matched_text}" → {ev.matched_rule}{" "}
                (weight {(ev.weight ?? 0).toFixed(2)})
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

// Phase 5: grouped, explainable view of a fill plan.
export function FieldMappingReview({ plan }: { plan: FillPlan }) {
  const grouped: Record<FieldAction, FieldMapping[]> = {
    fill: [],
    suggest: [],
    manual_review: [],
    skip: [],
  };
  for (const mapping of plan.mappings ?? []) {
    const bucket = grouped[mapping.action];
    if (bucket) {
      bucket.push(mapping);
    } else {
      grouped.manual_review.push(mapping);
    }
  }

  return (
    <div className="mapping-review">
      <div className="counts">
        <span className="pill pill-fill">Will fill: {plan.fill_count}</span>
        <span className="pill pill-suggest">Suggestions: {plan.suggest_count}</span>
        <span className="pill pill-manual">
          Manual review: {plan.manual_review_count}
        </span>
        <span className="pill pill-skip">Skipped: {plan.skip_count}</span>
      </div>

      {(plan.warnings ?? []).length > 0 && (
        <ul className="muted plan-warnings">
          {(plan.warnings ?? []).map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}

      {GROUP_ORDER.map((action) =>
        grouped[action].length > 0 ? (
          <div key={action} className="mapping-group">
            <h4>
              {ACTION_LABELS[action]} ({grouped[action].length})
            </h4>
            <ul className="mapping-list">
              {grouped[action].map((mapping) => (
                <MappingRow key={mapping.field_id} mapping={mapping} />
              ))}
            </ul>
          </div>
        ) : null,
      )}
    </div>
  );
}
