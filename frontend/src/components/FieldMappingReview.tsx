import { useState } from "react";
import {
  GROUP_INFO,
  GROUP_ORDER,
  confidenceLevel,
  groupMappings,
  groupOf,
} from "../lib/decisions";
import type { FieldMapping, FillPlan } from "../types/automation";

function fieldLabel(mapping: FieldMapping): string {
  return mapping.field_label || mapping.profile_path || mapping.selector;
}

function MappingRow({ mapping }: { mapping: FieldMapping }) {
  const [expanded, setExpanded] = useState(false);
  const group = groupOf(mapping);
  const confidence = mapping.confidence ?? 0;

  return (
    <li className={`mapping-row group-${group}`}>
      <div className="mapping-row-head">
        <span className="mapping-name">{fieldLabel(mapping)}</span>
        <span className={`status-badge status-${group}`}>{GROUP_INFO[group].label}</span>
      </div>
      <p className="mapping-reason">{mapping.reason}</p>
      <div className="mapping-meta">
        {(group === "fill" || group === "suggest" || group === "manual_review") && (
          <span title="High is 0.90 or more (fills), Medium is 0.60 or more (suggests)">
            {confidenceLevel(confidence)} confidence{" "}
            <span className="num">({confidence.toFixed(2)})</span>
          </span>
        )}
        <span>
          Category <code>{mapping.category}</code>
        </span>
        {mapping.value_preview && (
          <span>
            Value <code>{mapping.value_preview}</code>
          </span>
        )}
        {mapping.missing_value && <span className="meta-flag">No profile value</span>}
      </div>
      {mapping.warnings.map((w, i) => (
        <p key={i} className="notice notice-warn mapping-warning">
          {w}
        </p>
      ))}
      {mapping.evidence.length > 0 && (
        <button
          type="button"
          className="link-button"
          aria-expanded={expanded}
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? "Hide evidence" : `Why? Show evidence (${mapping.evidence.length})`}
        </button>
      )}
      {expanded && (
        <ul className="evidence-list">
          {mapping.evidence.map((ev, i) => (
            <li key={i}>
              <code>{ev.source}</code> matched “{ev.matched_text}” via {ev.matched_rule}{" "}
              <span className="num">(weight {(ev.weight ?? 0).toFixed(2)})</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

// Grouped, explainable view of a fill plan. Values are the backend's redacted
// previews only. Plan-level warnings are not listed separately: each one is
// shown on the row it came from.
export function FieldMappingReview({ plan }: { plan: FillPlan }) {
  const groups = groupMappings(plan);

  return (
    <div className="mapping-review">
      <dl className="stat-row">
        {GROUP_ORDER.map((group) => (
          <div key={group} className={`stat stat-${group}`}>
            <dt>{GROUP_INFO[group].label}</dt>
            <dd className="num">{groups[group].length}</dd>
          </div>
        ))}
      </dl>

      {GROUP_ORDER.map((group) =>
        groups[group].length > 0 ? (
          <details key={group} className="mapping-group" open={group !== "skip"}>
            <summary>
              <span className={`status-dot status-${group}`} aria-hidden="true" />
              {GROUP_INFO[group].label}
              <span className="num group-count">{groups[group].length}</span>
              <span className="group-hint">{GROUP_INFO[group].hint}</span>
            </summary>
            <ul className="mapping-list">
              {groups[group].map((mapping) => (
                <MappingRow key={mapping.field_id} mapping={mapping} />
              ))}
            </ul>
          </details>
        ) : null,
      )}
    </div>
  );
}
