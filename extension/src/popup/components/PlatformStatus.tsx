/**
 * What the extension thinks the current page is (Phase 7).
 *
 * Shows the platform, whether the page is supported, and the evidence behind that
 * conclusion. The evidence matters: a user who sees "Unsupported page" deserves to
 * know it was decided from the hostname, not from something invisible.
 *
 * The `safety` prop comes from the backend and is authoritative. `detection` is
 * advisory, and the two are shown separately rather than merged.
 */

import { PLATFORM_LABELS } from "../../shared/constants";
import type {
  PageSafetyDecision,
  PlatformDetection,
} from "../../shared/platformTypes";

function StatusDot({ state }: { state: "ok" | "warn" | "bad" | "idle" }) {
  return <span className={`dot ${state === "idle" ? "" : state}`} />;
}

export interface PlatformStatusProps {
  pageUrl: string;
  detection: PlatformDetection | null;
  safety: PageSafetyDecision | null;
  checking: boolean;
  /** Set when the platform check itself failed (backend down, for example). */
  error: string | null;
}

export function PlatformStatus({
  pageUrl,
  detection,
  safety,
  checking,
  error,
}: PlatformStatusProps) {
  const platformId = safety?.platform_id ?? detection?.platform_id ?? null;
  const label = platformId
    ? (PLATFORM_LABELS[platformId] ?? detection?.display_name ?? platformId)
    : "Unknown";

  const state: "ok" | "warn" | "bad" | "idle" = error
    ? "bad"
    : checking || !safety
      ? "idle"
      : !safety.allowed
        ? "bad"
        : safety.requires_user_confirmation
          ? "warn"
          : "ok";

  return (
    <section>
      <h2>Current page</h2>
      <div className="status">
        <div className="status-line">
          <StatusDot state={state} />
          <p className="page-url">{pageUrl || "unknown"}</p>
        </div>
        <div className="status-line">
          <StatusDot state={state} />
          <span>
            <strong>{label}</strong>
            {error
              ? ` - could not check: ${error}`
              : checking
                ? " - checking..."
                : safety
                  ? ` - ${safety.allowed ? "supported" : "not supported"}`
                  : ""}
          </span>
        </div>
        {safety && !safety.allowed && (safety.blocked_reason || safety.reason) && (
          <div className="status-line">
            <span className="reason">{safety.blocked_reason || safety.reason}</span>
          </div>
        )}
        {detection && detection.matched_by.length > 0 && (
          <div className="status-line">
            <span className="evidence" title={detection.matched_by.join("\n")}>
              Matched by: {detection.matched_by.join(", ")}
            </span>
          </div>
        )}
      </div>
    </section>
  );
}
