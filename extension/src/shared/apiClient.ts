/**
 * Client for the local FastAPI backend.
 *
 * Only ever talks to a loopback origin. There are no cloud calls, no analytics,
 * and no API keys anywhere in this extension.
 */

import {
  DEFAULT_BACKEND_URL,
  PATH_ANALYZE_REAL_PAGE,
  PATH_CHECK_URL,
} from "./constants";
import type {
  CheckUrlResponse,
  RealPlatformAnalyzeRequest,
  RealPlatformAnalyzeResponse,
} from "./platformTypes";
import type {
  ExtensionAnalyzeRequest,
  ExtensionAnalyzeResponse,
  ExtensionHealthResponse,
} from "./types";

/** Thrown for both transport failures and non-2xx responses. */
export class BackendError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "BackendError";
    this.status = status;
  }
}

function normalizeBackendUrl(backendUrl: string): string {
  return backendUrl.replace(/\/+$/, "") || DEFAULT_BACKEND_URL;
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Non-JSON error body; fall through to the generic message.
  }
  return `${response.status} ${response.statusText}`;
}

async function request<T>(
  backendUrl: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${normalizeBackendUrl(backendUrl)}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch (error) {
    throw new BackendError(
      `Cannot reach the local backend at ${normalizeBackendUrl(backendUrl)}. ` +
        `Start it with "uvicorn app.main:app --reload" from the backend folder. ` +
        `(${error instanceof Error ? error.message : String(error)})`,
    );
  }
  if (!response.ok) {
    throw new BackendError(await readErrorDetail(response), response.status);
  }
  return (await response.json()) as T;
}

export function getExtensionHealth(
  backendUrl: string = DEFAULT_BACKEND_URL,
): Promise<ExtensionHealthResponse> {
  return request<ExtensionHealthResponse>(backendUrl, "/extension/health");
}

export function analyzeCurrentPage(
  payload: ExtensionAnalyzeRequest,
  backendUrl: string = DEFAULT_BACKEND_URL,
): Promise<ExtensionAnalyzeResponse> {
  return request<ExtensionAnalyzeResponse>(backendUrl, "/extension/analyze-page", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Phase 7: ask whether a page may be analyzed. The backend evaluates the URL
 * string only - it does not fetch the page.
 */
export function checkPageUrl(
  pageUrl: string,
  backendUrl: string = DEFAULT_BACKEND_URL,
): Promise<CheckUrlResponse> {
  return request<CheckUrlResponse>(backendUrl, PATH_CHECK_URL, {
    method: "POST",
    body: JSON.stringify({ page_url: pageUrl }),
  });
}

/**
 * Phase 7: analyze a real application page.
 *
 * The backend rejects this with a 400 unless the page is on a supported platform
 * *and* `user_confirmed_real_page` is true, so callers must not paper over the
 * confirmation. The response's `instructions` are transient: hand them to the
 * content script and drop them.
 */
export function analyzeRealPage(
  payload: RealPlatformAnalyzeRequest,
  backendUrl: string = DEFAULT_BACKEND_URL,
): Promise<RealPlatformAnalyzeResponse> {
  return request<RealPlatformAnalyzeResponse>(backendUrl, PATH_ANALYZE_REAL_PAGE, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
