/**
 * Popup UI (Phase 6).
 *
 * The popup is the orchestrator: it talks to the local backend and to the content
 * script, and holds the analysis result in React state only. Nothing here is
 * written to chrome.storage except the backend URL setting, so closing the popup
 * discards every profile value the backend returned.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ACTION_FILL,
  ACTION_LABELS,
  ACTION_MANUAL_REVIEW,
  ACTION_SKIP,
  ACTION_SUGGEST,
  ALLOWED_PAGE_ORIGINS,
  DEFAULT_BACKEND_URL,
  MSG_APPLY_FILL_INSTRUCTIONS,
  MSG_CLEAR_HIGHLIGHTS,
  MSG_DETECT_FIELDS,
  MSG_HIGHLIGHT_FIELDS,
  STORAGE_KEY_BACKEND_URL,
} from "../shared/constants";
import {
  analyzeCurrentPage,
  getExtensionHealth,
  isAllowedPageUrl,
} from "../shared/apiClient";
import type {
  ApplyFillResult,
  ContentMessage,
  ContentResponse,
  DetectFieldsResult,
  ExtensionAnalyzeResponse,
  ExtensionDetectedField,
  ExtensionHealthResponse,
  FieldMapping,
} from "../shared/types";

const ACTION_ORDER = [
  ACTION_FILL,
  ACTION_SUGGEST,
  ACTION_MANUAL_REVIEW,
  ACTION_SKIP,
] as const;

/** Send a message to the active tab's content script with a readable failure. */
async function sendToContentScript<T>(
  tabId: number,
  message: ContentMessage,
): Promise<T> {
  let response: ContentResponse<T> | undefined;
  try {
    response = (await chrome.tabs.sendMessage(tabId, message)) as ContentResponse<T>;
  } catch (error) {
    throw new Error(
      "Could not reach the page. Reload the tab (the content script is injected " +
        `on page load) and try again. (${
          error instanceof Error ? error.message : String(error)
        })`,
    );
  }
  if (!response) {
    throw new Error("The page did not respond. Reload the tab and try again.");
  }
  if (!response.ok) {
    throw new Error(response.error);
  }
  return response.data;
}

/** Best-effort label for a field, using the same signals the backend classifies on. */
function fieldLabel(field: ExtensionDetectedField | undefined, fallback: string): string {
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

function StatusDot({ state }: { state: "ok" | "warn" | "bad" | "idle" }) {
  return <span className={`dot ${state === "idle" ? "" : state}`} />;
}

function MappingRow({
  mapping,
  label,
}: {
  mapping: FieldMapping;
  label: string;
}) {
  return (
    <div className="row">
      <div className="row-head">
        <span className="row-name" title={label}>
          {label}
        </span>
        <span>
          {mapping.sensitive && <span className="badge sensitive">Sensitive</span>}{" "}
          <span className={`badge ${mapping.action}`}>
            {ACTION_LABELS[mapping.action] ?? mapping.action}
          </span>
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
      {mapping.reason && <div className="row-reason">{mapping.reason}</div>}
    </div>
  );
}

export function Popup() {
  const [backendUrl, setBackendUrl] = useState(DEFAULT_BACKEND_URL);
  const [tabId, setTabId] = useState<number | null>(null);
  const [pageUrl, setPageUrl] = useState<string>("");
  const [health, setHealth] = useState<ExtensionHealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [detected, setDetected] = useState<DetectFieldsResult | null>(null);
  const [analysis, setAnalysis] = useState<ExtensionAnalyzeResponse | null>(null);
  const [applyResult, setApplyResult] = useState<ApplyFillResult | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const pageAllowed = isAllowedPageUrl(pageUrl);

  useEffect(() => {
    void (async () => {
      const stored = await chrome.storage.local.get(STORAGE_KEY_BACKEND_URL);
      const url = (stored[STORAGE_KEY_BACKEND_URL] as string) || DEFAULT_BACKEND_URL;
      setBackendUrl(url);

      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      setTabId(tab?.id ?? null);
      setPageUrl(tab?.url ?? "");

      try {
        setHealth(await getExtensionHealth(url));
      } catch (err) {
        setHealthError(err instanceof Error ? err.message : String(err));
      }
    })();
  }, []);

  /** Run an async action with uniform busy/error handling. */
  const run = useCallback(
    async (label: string, action: () => Promise<string | null>) => {
      setBusy(true);
      setError(null);
      setStatus(null);
      try {
        setStatus(await action());
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        console.warn(`${label} failed`, err);
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const handleDetect = () =>
    run("Detect fields", async () => {
      if (tabId === null) throw new Error("No active tab was found.");
      const result = await sendToContentScript<DetectFieldsResult>(tabId, {
        type: MSG_DETECT_FIELDS,
      });
      setDetected(result);
      setAnalysis(null);
      setApplyResult(null);
      return `Detected ${result.fields.length} field(s).`;
    });

  const handleAnalyze = () =>
    run("Analyze", async () => {
      if (!detected) throw new Error("Run 'Detect fields' first.");
      const result = await analyzeCurrentPage(
        {
          page_url: detected.page_url,
          page_title: detected.page_title,
          // Reuse the sample form's file name so Phase 5 mapping overrides match.
          form_name: new URL(detected.page_url).pathname.split("/").pop() ?? null,
          fields: detected.fields,
        },
        backendUrl,
      );
      setAnalysis(result);
      setApplyResult(null);
      const plan = result.fill_plan;
      return `Plan ready: ${plan.fill_count} fill, ${plan.suggest_count} suggest, ${plan.manual_review_count} manual review, ${plan.skip_count} skip.`;
    });

  const handleHighlight = () =>
    run("Highlight", async () => {
      if (tabId === null) throw new Error("No active tab was found.");
      if (!analysis) throw new Error("Analyze the page first.");
      const { marked } = await sendToContentScript<{ marked: number }>(tabId, {
        type: MSG_HIGHLIGHT_FIELDS,
        mappings: analysis.fill_plan.mappings,
      });
      return `Highlighted ${marked} field(s) on the page.`;
    });

  const handleApply = () =>
    run("Apply safe fills", async () => {
      if (tabId === null) throw new Error("No active tab was found.");
      if (!analysis) throw new Error("Analyze the page first.");
      const result = await sendToContentScript<ApplyFillResult>(tabId, {
        type: MSG_APPLY_FILL_INSTRUCTIONS,
        instructions: analysis.instructions,
      });
      setApplyResult(result);
      return `Filled ${result.filled}, skipped ${result.skipped}, failed ${result.failed}. Nothing was submitted.`;
    });

  const handleClear = () =>
    run("Clear highlights", async () => {
      if (tabId === null) throw new Error("No active tab was found.");
      const { cleared } = await sendToContentScript<{ cleared: number }>(tabId, {
        type: MSG_CLEAR_HIGHLIGHTS,
      });
      return `Cleared highlights on ${cleared} field(s).`;
    });

  const fieldsById = useMemo(() => {
    const map = new Map<string, ExtensionDetectedField>();
    for (const field of detected?.fields ?? []) {
      map.set(field.field_id, field);
    }
    return map;
  }, [detected]);

  const groupedMappings = useMemo(() => {
    const groups = new Map<string, FieldMapping[]>(
      ACTION_ORDER.map((action) => [action, [] as FieldMapping[]]),
    );
    for (const mapping of analysis?.fill_plan.mappings ?? []) {
      (groups.get(mapping.action) ?? groups.get(ACTION_MANUAL_REVIEW)!).push(mapping);
    }
    return groups;
  }, [analysis]);

  const plan = analysis?.fill_plan;
  const planWarnings = [
    ...(analysis?.warnings ?? []),
    ...(plan?.warnings ?? []),
    ...(detected?.warnings ?? []),
    ...(applyResult?.warnings ?? []),
  ];

  return (
    <div className="popup">
      <h1>Autofill Assistant</h1>
      <p className="tagline">
        Phase 6 prototype - local sample forms only. Nothing is ever submitted.
      </p>

      <section>
        <h2>Backend</h2>
        <div className="status">
          <div className="status-line">
            <StatusDot state={healthError ? "bad" : health?.ok ? "ok" : "idle"} />
            <span>
              {healthError
                ? healthError
                : health
                  ? health.backend
                  : "Checking the local backend..."}
            </span>
          </div>
          {health && (
            <div className="status-line">
              <StatusDot
                state={
                  !health.profile_exists
                    ? "bad"
                    : health.profile_needs_review
                      ? "warn"
                      : "ok"
                }
              />
              <span>{health.message}</span>
            </div>
          )}
        </div>
      </section>

      <section>
        <h2>Current page</h2>
        <div className="status">
          <div className="status-line">
            <StatusDot state={pageAllowed ? "ok" : "warn"} />
            <p className="page-url">{pageUrl || "unknown"}</p>
          </div>
        </div>
        {!pageAllowed && (
          <div className="notice warn" style={{ marginTop: 8 }}>
            This page is not supported in Phase 6. The extension only works on local
            development pages:
            <ul>
              {ALLOWED_PAGE_ORIGINS.map((origin) => (
                <li key={origin}>{origin}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section>
        <h2>Actions</h2>
        <div className="actions">
          <button onClick={handleDetect} disabled={busy || !pageAllowed}>
            Detect fields
          </button>
          <button onClick={handleAnalyze} disabled={busy || !detected}>
            Analyze with local profile
          </button>
          <button onClick={handleHighlight} disabled={busy || !analysis}>
            Highlight decisions
          </button>
          <button onClick={handleClear} disabled={busy}>
            Clear highlights
          </button>
          <button
            className="primary wide"
            onClick={handleApply}
            disabled={busy || !analysis || (plan?.fill_count ?? 0) === 0}
          >
            Apply safe fills{plan ? ` (${plan.fill_count})` : ""}
          </button>
        </div>
      </section>

      {status && <div className="notice">{status}</div>}
      {error && <div className="notice bad">{error}</div>}

      <section>
        <h2>Counts</h2>
        <div className="counts">
          <div className="count">
            <span className="value">{detected?.fields.length ?? 0}</span>
            <span className="label">Detected</span>
          </div>
          {ACTION_ORDER.map((action) => (
            <div className={`count ${action}`} key={action}>
              <span className="value">
                {action === ACTION_FILL
                  ? (plan?.fill_count ?? 0)
                  : action === ACTION_SUGGEST
                    ? (plan?.suggest_count ?? 0)
                    : action === ACTION_MANUAL_REVIEW
                      ? (plan?.manual_review_count ?? 0)
                      : (plan?.skip_count ?? 0)}
              </span>
              <span className="label">{ACTION_LABELS[action]}</span>
            </div>
          ))}
        </div>
      </section>

      {planWarnings.length > 0 && (
        <section>
          <h2>Warnings</h2>
          <div className="notice warn">
            <ul>
              {planWarnings.map((warning, index) => (
                <li key={`${index}-${warning}`}>{warning}</li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {plan && (
        <section>
          <h2>Fill plan review</h2>
          <div className="review">
            {ACTION_ORDER.flatMap((action) =>
              (groupedMappings.get(action) ?? []).map((mapping) => (
                <MappingRow
                  key={mapping.field_id}
                  mapping={mapping}
                  label={fieldLabel(fieldsById.get(mapping.field_id), mapping.field_id)}
                />
              )),
            )}
          </div>
        </section>
      )}

      <div className="footnote">
        <strong>What this prototype will not do:</strong>
        <ul>
          <li>Submit a form or click any button.</li>
          <li>Autofill sensitive or legal questions - answer those yourself.</li>
          <li>Fill passwords or attach files.</li>
          <li>Work on real job sites; only local sample forms are supported.</li>
        </ul>
        Always read the whole form yourself before submitting it.
      </div>
    </div>
  );
}
