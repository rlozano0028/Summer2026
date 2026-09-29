/**
 * Popup UI.
 *
 * The popup is the orchestrator: it talks to the local backend and to the content
 * script, and holds the analysis result in React state only. Nothing here is written
 * to chrome.storage except the backend URL setting, so closing the popup discards
 * every profile value the backend returned.
 *
 * Two flows share one screen, and which one runs is decided by the page URL:
 *
 * - Loopback pages take the Phase 6 path unchanged: `POST /extension/analyze-page`,
 *   no confirmation, content script already injected declaratively.
 * - Real pages take the Phase 7 path: the backend is asked whether the page is
 *   supported, the user must tick a confirmation, the content script is injected on
 *   demand under `activeTab`, and `POST /extension/analyze-real-page` is used.
 *
 * The gate is the URL rather than a setting, so there is no way to accidentally put
 * a real page through the local path or vice versa.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ALLOWED_PAGE_ORIGINS,
  DEFAULT_BACKEND_URL,
  MSG_APPLY_FILL_INSTRUCTIONS,
  MSG_CLEAR_HIGHLIGHTS,
  MSG_DETECT_FIELDS,
  MSG_HIGHLIGHT_FIELDS,
  MSG_PING,
  PLATFORM_LABELS,
  STORAGE_KEY_BACKEND_URL,
} from "../shared/constants";
import {
  analyzeCurrentPage,
  analyzeRealPage,
  checkPageUrl,
  getExtensionHealth,
} from "../shared/apiClient";
import { describeTabAccessProblem } from "../shared/permissions";
import type { PageSafetyDecision, PlatformDetection } from "../shared/platformTypes";
import type {
  ApplyFillResult,
  ContentMessage,
  ContentResponse,
  DetectFieldsResult,
  ExtensionFillInstruction,
  ExtensionHealthResponse,
  FillPlan,
} from "../shared/types";
import { isLocalUrl } from "../shared/urlSafety";
import { FillPlanReview } from "./components/FillPlanReview";
import { PlatformStatus } from "./components/PlatformStatus";
import { RealPageWarning } from "./components/RealPageWarning";
import { GROUP_INFO, GROUP_ORDER, buildReview, stepState } from "./decisions";

/** The bundled content script, injected on demand for non-loopback pages. */
const CONTENT_SCRIPT_FILE = "content/contentScript.js";

/** Whatever produced the current plan, reduced to what the UI needs. */
interface AnalysisState {
  fill_plan: FillPlan;
  instructions: ExtensionFillInstruction[];
  warnings: string[];
  unsupported_count: number;
}

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
      "Could not reach the page. Reload the tab and try again. " +
        `(${error instanceof Error ? error.message : String(error)})`,
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

/**
 * Make sure the content script is present in `tabId`, injecting it if not.
 *
 * On loopback pages the manifest already injected it. On a real page nothing is
 * present until this runs, and this only runs because the user clicked a button -
 * that is what `activeTab` grants and the reason no broad host permission is needed.
 * The content script guards against double registration, so injecting twice is safe.
 */
async function ensureContentScript(tabId: number): Promise<void> {
  try {
    await sendToContentScript<{ ready: boolean }>(tabId, { type: MSG_PING });
    return;
  } catch {
    // Not injected yet, which is the normal case for a real page.
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: [CONTENT_SCRIPT_FILE],
    });
  } catch (error) {
    throw new Error(
      "Could not attach to this page. Focus the tab and try again; some pages " +
        `(browser settings, extension pages, PDF viewers) cannot be read. (${
          error instanceof Error ? error.message : String(error)
        })`,
    );
  }
}

function StatusDot({ state }: { state: "ok" | "warn" | "bad" | "idle" }) {
  return <span className={`dot ${state === "idle" ? "" : state}`} />;
}

export function Popup() {
  const [backendUrl, setBackendUrl] = useState(DEFAULT_BACKEND_URL);
  const [tabId, setTabId] = useState<number | null>(null);
  const [pageUrl, setPageUrl] = useState<string>("");
  const [health, setHealth] = useState<ExtensionHealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [detection, setDetection] = useState<PlatformDetection | null>(null);
  const [safety, setSafety] = useState<PageSafetyDecision | null>(null);
  const [platformError, setPlatformError] = useState<string | null>(null);
  const [checkingPlatform, setCheckingPlatform] = useState(true);
  const [confirmedRealPage, setConfirmedRealPage] = useState(false);
  const [detected, setDetected] = useState<DetectFieldsResult | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisState | null>(null);
  const [applyResult, setApplyResult] = useState<ApplyFillResult | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [highlighted, setHighlighted] = useState(false);
  const [activeStep, setActiveStep] = useState<1 | 2 | 3>(1);

  const isLocalPage = isLocalUrl(pageUrl);
  const tabProblem = describeTabAccessProblem(pageUrl);
  const needsConfirmation = safety?.requires_user_confirmation === true;
  const pageAllowed = safety?.allowed === true && tabProblem === null;
  const canAnalyze = pageAllowed && (!needsConfirmation || confirmedRealPage);
  const unsupportedCount =
    detected?.fields.filter((field) => field.is_custom_control).length ?? 0;

  useEffect(() => {
    void (async () => {
      const stored = await chrome.storage.local.get(STORAGE_KEY_BACKEND_URL);
      const url = (stored[STORAGE_KEY_BACKEND_URL] as string) || DEFAULT_BACKEND_URL;
      setBackendUrl(url);

      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      setTabId(tab?.id ?? null);
      const currentUrl = tab?.url ?? "";
      setPageUrl(currentUrl);

      try {
        setHealth(await getExtensionHealth(url));
      } catch (err) {
        setHealthError(err instanceof Error ? err.message : String(err));
      }

      // Ask the backend about the URL. This is a string check on its side: the page
      // is never fetched, and asking does not touch the tab at all.
      try {
        const result = await checkPageUrl(currentUrl, url);
        setDetection(result.detection);
        setSafety(result.safety);
      } catch (err) {
        setPlatformError(err instanceof Error ? err.message : String(err));
      } finally {
        setCheckingPlatform(false);
      }
    })();
  }, []);

  /** Run an async action with uniform busy/error handling. */
  const run = useCallback(
    async (label: string, step: 1 | 2 | 3, action: () => Promise<string | null>) => {
      setActiveStep(step);
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
    run("Detect fields", 1, async () => {
      if (tabId === null) throw new Error("No active tab was found.");
      if (!canAnalyze) {
        throw new Error(
          needsConfirmation && !confirmedRealPage
            ? "Confirm that you want this real page analyzed first."
            : (safety?.blocked_reason ?? "This page is not supported."),
        );
      }
      await ensureContentScript(tabId);
      const result = await sendToContentScript<DetectFieldsResult>(tabId, {
        type: MSG_DETECT_FIELDS,
      });
      setDetected(result);
      setAnalysis(null);
      setApplyResult(null);
      const custom = result.fields.filter((field) => field.is_custom_control).length;
      return (
        `Detected ${result.fields.length} field(s)` +
        (custom > 0 ? `, ${custom} of them unsupported custom controls.` : ".")
      );
    });

  const handleAnalyze = () =>
    run("Analyze", 2, async () => {
      if (!detected) throw new Error("Run 'Detect fields' first.");
      if (!canAnalyze) throw new Error("This page is not approved for analysis.");

      if (isLocalPage) {
        // Phase 6 path, byte for byte: same endpoint, same payload, same form-name
        // trick so local mapping overrides keep applying.
        const result = await analyzeCurrentPage(
          {
            page_url: detected.page_url,
            page_title: detected.page_title,
            form_name: new URL(detected.page_url).pathname.split("/").pop() ?? null,
            fields: detected.fields,
          },
          backendUrl,
        );
        setAnalysis({
          fill_plan: result.fill_plan,
          instructions: result.instructions,
          warnings: result.warnings,
          unsupported_count: detected.fields.filter((f) => f.is_custom_control).length,
        });
      } else {
        const result = await analyzeRealPage(
          {
            page_url: detected.page_url,
            page_title: detected.page_title,
            platform_id: detected.platform_id ?? null,
            platform_confidence: detected.platform_confidence ?? null,
            user_confirmed_real_page: confirmedRealPage,
            fields: detected.fields,
          },
          backendUrl,
        );
        setAnalysis({
          fill_plan: result.fill_plan,
          instructions: result.instructions,
          warnings: result.warnings,
          unsupported_count: result.unsupported_count,
        });
        setSafety(result.safety);
        if (result.platform) setDetection(result.platform);
      }
      setApplyResult(null);
      return "Plan ready. Check the Will fill list before filling anything.";
    });

  const handleHighlight = () =>
    run("Highlight", 3, async () => {
      if (tabId === null) throw new Error("No active tab was found.");
      if (!analysis) throw new Error("Analyze the page first.");
      await ensureContentScript(tabId);
      const { marked } = await sendToContentScript<{ marked: number }>(tabId, {
        type: MSG_HIGHLIGHT_FIELDS,
        mappings: analysis.fill_plan.mappings,
      });
      setHighlighted(true);
      return `Highlighted ${marked} field(s) on the page.`;
    });

  const handleApply = () =>
    run("Apply safe fills", 3, async () => {
      if (tabId === null) throw new Error("No active tab was found.");
      if (!analysis) throw new Error("Analyze the page first.");
      if (!canAnalyze) throw new Error("This page is not approved for filling.");
      await ensureContentScript(tabId);
      const result = await sendToContentScript<ApplyFillResult>(tabId, {
        type: MSG_APPLY_FILL_INSTRUCTIONS,
        instructions: analysis.instructions,
      });
      setApplyResult(result);
      return (
        `Filled ${result.filled}, skipped ${result.skipped}, failed ${result.failed}. ` +
        "Nothing was submitted. Check the whole form, then submit it yourself."
      );
    });

  const handleClear = () =>
    run("Clear highlights", 3, async () => {
      if (tabId === null) throw new Error("No active tab was found.");
      await ensureContentScript(tabId);
      const { cleared } = await sendToContentScript<{ cleared: number }>(tabId, {
        type: MSG_CLEAR_HIGHLIGHTS,
      });
      setHighlighted(false);
      return `Cleared highlights on ${cleared} field(s).`;
    });

  const plan = analysis?.fill_plan;
  const review = useMemo(
    () => (plan ? buildReview(plan, detected?.fields ?? []) : null),
    [plan, detected],
  );
  const fillCount = review?.fill.length ?? 0;
  const steps = stepState({
    busy,
    backendOk: health?.ok === true,
    profileExists: health?.profile_exists === true,
    checkingPage: checkingPlatform,
    pageAllowed,
    needsConfirmation,
    confirmed: confirmedRealPage,
    detected: detected !== null,
    analyzed: analysis !== null,
    fillCount,
  });

  const allWarnings = [
    ...(analysis?.warnings ?? []),
    ...(plan?.warnings ?? []),
    ...(detected?.warnings ?? []),
    ...(applyResult?.warnings ?? []),
  ].filter((warning, index, list) => list.indexOf(warning) === index);

  const platformLabel =
    PLATFORM_LABELS[safety?.platform_id ?? detection?.platform_id ?? ""] ??
    detection?.display_name ??
    "this";

  const profileDot: "ok" | "warn" | "bad" = !health?.profile_exists
    ? "bad"
    : health.profile_needs_review
      ? "warn"
      : "ok";
  const profileText = !health?.profile_exists
    ? "none saved yet. Create one in the dashboard."
    : health.profile_needs_review
      ? "saved but not marked reviewed. Check it in the dashboard."
      : "reviewed and ready.";

  const messages = (step: 1 | 2 | 3) =>
    activeStep === step && (status || error) ? (
      <div className={`notice step-notice ${error ? "bad" : "ok"}`} role={error ? "alert" : "status"}>
        {error ?? status}
      </div>
    ) : null;

  return (
    <div className="popup">
      <header className="popup-header">
        <h1>Autofill Assistant</h1>
        <p className="tagline">You review. You submit. Nothing is ever submitted for you.</p>
      </header>

      <div className="status">
        <div className="status-line">
          <StatusDot state={healthError ? "bad" : health?.ok ? "ok" : "idle"} />
          <span>
            <strong>Backend</strong>{" "}
            {healthError
              ? "not reachable. Start it with uvicorn from the backend folder."
              : health
                ? "connected"
                : "checking…"}
          </span>
        </div>
        {health && (
          <div className="status-line">
            <StatusDot state={profileDot} />
            <span>
              <strong>Profile</strong> {profileText}
            </span>
          </div>
        )}
      </div>

      <PlatformStatus
        pageUrl={pageUrl}
        detection={detection}
        safety={safety}
        checking={checkingPlatform}
        error={platformError}
      />

      {tabProblem && <div className="notice bad">{tabProblem}</div>}

      {!checkingPlatform && safety && !safety.allowed && !tabProblem && (
        <div className="notice">
          Supported: Greenhouse, Lever, Ashby, Workday, and SmartRecruiters pages, company
          domains you approved in the backend, and local test pages on{" "}
          {ALLOWED_PAGE_ORIGINS.join(", ")}.
        </div>
      )}

      {needsConfirmation && pageAllowed && (
        <RealPageWarning
          platformLabel={platformLabel}
          warnings={safety?.warnings ?? []}
          confirmed={confirmedRealPage}
          onConfirmedChange={setConfirmedRealPage}
          disabled={busy}
        />
      )}

      {steps.blocker && !busy && <div className="notice">{steps.blocker}</div>}

      <ol className="steps">
        <li className={detected ? "done" : ""}>
          <div className="step-head">
            <span className="step-num">1</span>
            <span className="step-title">Scan this page</span>
            <button onClick={handleDetect} disabled={!steps.canDetect}>
              {detected ? "Scan again" : "Scan"}
            </button>
          </div>
          {messages(1)}
          {detected && (
            <p className="step-result">
              {detected.fields.length} field(s) found
              {unsupportedCount > 0
                ? `, ${unsupportedCount} of them custom controls the extension will not touch`
                : ""}
              .
            </p>
          )}
        </li>

        <li className={analysis ? "done" : ""}>
          <div className="step-head">
            <span className="step-num">2</span>
            <span className="step-title">Build a fill plan</span>
            <button onClick={handleAnalyze} disabled={!steps.canAnalyze}>
              {analysis ? "Rebuild" : "Build plan"}
            </button>
          </div>
          {messages(2)}
          {review && (
            <div className="mini-counts">
              {GROUP_ORDER.map((group) => (
                <span key={group} className={`mini status-${group}`}>
                  <span className="num">{review[group].length}</span> {GROUP_INFO[group].label}
                </span>
              ))}
            </div>
          )}
        </li>

        <li className={applyResult ? "done" : ""}>
          <div className="step-head">
            <span className="step-num">3</span>
            <span className="step-title">Review, then fill</span>
          </div>
          {plan && <FillPlanReview plan={plan} fields={detected?.fields ?? []} />}
          {analysis && (
            <div className="highlight-row">
              <button onClick={handleHighlight} disabled={busy}>
                Highlight on page
              </button>
              <button onClick={handleClear} disabled={busy || !highlighted}>
                Clear highlights
              </button>
            </div>
          )}
          <button className="primary wide" onClick={handleApply} disabled={!steps.canApply}>
            {analysis
              ? `Fill ${fillCount} safe field${fillCount === 1 ? "" : "s"}`
              : "Fill safe fields"}
          </button>
          {messages(3)}
          <p className="submit-note">
            Only the fields under “Will fill” are typed in. Nothing is submitted: you check
            the whole form and click Submit yourself.
          </p>
        </li>
      </ol>


      {allWarnings.length > 0 && (
        <details className="warnings">
          <summary>
            {allWarnings.length} note{allWarnings.length === 1 ? "" : "s"} about this page
          </summary>
          <ul>
            {allWarnings.map((warning, index) => (
              <li key={`${index}-${warning}`}>{warning}</li>
            ))}
          </ul>
        </details>
      )}

      <details className="footnote">
        <summary>What this extension never does</summary>
        <ul>
          <li>Submit a form, or click Apply, Next, or any other button.</li>
          <li>
            Fill sensitive or legal questions (work authorization, sponsorship, salary,
            EEO, criminal history).
          </li>
          <li>Fill passwords or hidden fields, or attach files.</li>
          <li>Run on a page you did not open and click the extension on.</li>
          <li>Store your profile in the browser or send it anywhere but your local backend.</li>
        </ul>
      </details>
    </div>
  );
}
