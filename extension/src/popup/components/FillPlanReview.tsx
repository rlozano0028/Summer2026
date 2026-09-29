/**
 * The reviewable fill plan, grouped the same way as the dashboard: Will fill,
 * Suggested, Needs review, Protected, Skipped. Will fill comes first because it
 * is the group the user must check before clicking Fill.
 *
 * Privacy: rows show the backend's redacted `value_preview` only. The real values
 * live in the transient instruction list and are never rendered.
 */

import { useState } from "react";

import type { ExtensionDetectedField, FillPlan } from "../../shared/types";
import {
  GROUP_INFO,
  GROUP_ORDER,
  buildReview,
  confidenceLevel,
  type ReviewRow,
} from "../decisions";

const UNSUPPORTED_REASON =
  "Custom control the extension cannot set safely. It will not be touched; fill it in yourself.";

function Row({ row }: { row: ReviewRow }) {
  const [open, setOpen] = useState(false);
  const { mapping, group, unsupported } = row;
  const scored = group === "fill" || group === "suggest" || group === "manual_review";

  return (
    <li className={`row group-${group}`}>
      <div className="row-head">
        <span className="row-name" title={row.label}>
          {row.label}
        </span>
        <span className={`badge status-${group}`}>
          {unsupported ? "Not supported" : GROUP_INFO[group].label}
        </span>
      </div>
      <div className="row-reason">{unsupported ? UNSUPPORTED_REASON : mapping.reason}</div>
      <div className="row-meta">
        {scored && !unsupported && (
          <span>
            {confidenceLevel(mapping.confidence ?? 0)} confidence{" "}
            <span className="num">({(mapping.confidence ?? 0).toFixed(2)})</span>
          </span>
        )}
        {mapping.value_preview && <span className="preview">{mapping.value_preview}</span>}
        {mapping.missing_value && <span className="flag">No profile value</span>}
        {(mapping.evidence ?? []).length > 0 && (
          <button
            type="button"
            className="link"
            aria-expanded={open}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? "Hide why" : "Why?"}
          </button>
        )}
      </div>
      {open && (
        <ul className="evidence-list">
          {(mapping.evidence ?? []).map((ev, index) => (
            <li key={index}>
              {ev.source} matched “{ev.matched_text}”{" "}
              <span className="num">({(ev.weight ?? 0).toFixed(2)})</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function FillPlanReview({
  plan,
  fields,
}: {
  plan: FillPlan;
  fields: ExtensionDetectedField[];
}) {
  const review = buildReview(plan, fields);

  return (
    <div className="review">
      {GROUP_ORDER.map((group) =>
        review[group].length > 0 ? (
          <details key={group} className="group" open={group === "fill"}>
            <summary>
              <span className={`dot status-${group}`} aria-hidden="true" />
              <span className="group-name">{GROUP_INFO[group].label}</span>
              <span className="num group-count">{review[group].length}</span>
            </summary>
            <p className="group-hint">{GROUP_INFO[group].hint}</p>
            <ul className="rows">
              {review[group].map((row) => (
                <Row key={row.mapping.field_id} row={row} />
              ))}
            </ul>
          </details>
        ) : null,
      )}
    </div>
  );
}
