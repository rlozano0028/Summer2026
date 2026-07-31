/**
 * Content script message handler.
 *
 * This script does nothing on load beyond registering a message listener. Every
 * action - detecting, highlighting, filling, clearing - happens only in response to
 * a message the user triggered by clicking a button in the popup. It never runs on a
 * schedule, never observes the page, and makes no backend calls of its own; the
 * popup orchestrates popup -> backend and popup -> content script so that page
 * context and network access stay separated.
 *
 * How it gets here differs by page, and that difference is the whole of Phase 7:
 *
 * - Loopback pages: injected declaratively via the manifest, exactly as in Phase 6.
 * - Real pages: injected by the popup with `chrome.scripting.executeScript` when the
 *   user clicks, under `activeTab`. Nothing is injected into a page the user did not
 *   activate.
 *
 * Because on-demand injection can happen more than once in a tab's lifetime, the
 * whole module is guarded: a second injection finds the listener already registered
 * and returns immediately, instead of registering a duplicate that would answer
 * every message twice.
 */

import {
  MSG_APPLY_FILL_INSTRUCTIONS,
  MSG_CLEAR_HIGHLIGHTS,
  MSG_DETECT_FIELDS,
  MSG_DETECT_PLATFORM,
  MSG_HIGHLIGHT_FIELDS,
  MSG_PING,
} from "../shared/constants";
import type { DetectPlatformResult } from "../shared/platformTypes";
import type {
  ApplyFillResult,
  ContentMessage,
  ContentResponse,
  DetectFieldsResult,
} from "../shared/types";
import { detectFields } from "./fieldDetector";
import { clearHighlights, highlightFields } from "./pageHighlighter";
import { detectCurrentPlatform, getActiveAdapter } from "./platformDetector";
import { applyFillInstructions } from "./safeFiller";

/** Marker on `window` proving a listener is already registered in this frame. */
const INJECTION_FLAG = "__autofillAssistantContentScriptReady";

interface GuardedWindow extends Window {
  [INJECTION_FLAG]?: boolean;
}

function ok<T>(data: T): ContentResponse<T> {
  return { ok: true, data };
}

function fail(error: unknown): ContentResponse<never> {
  return { ok: false, error: error instanceof Error ? error.message : String(error) };
}

function handleDetectPlatform(): ContentResponse<DetectPlatformResult> {
  return ok(detectCurrentPlatform(document));
}

/**
 * Detect fields, then let the platform adapter improve their metadata.
 *
 * The adapter only adds labels and flags. It cannot decide what to fill: that stays
 * with the Phase 5 engine in the backend.
 */
function handleDetect(): ContentResponse<DetectFieldsResult> {
  const platform = detectCurrentPlatform(document);
  const adapter = getActiveAdapter(document);
  const { fields, warnings } = detectFields(document);

  return ok({
    page_url: window.location.href,
    page_title: document.title,
    fields: adapter.enhanceDetectedFields(fields, document),
    warnings: [...warnings, ...platform.warnings],
    platform_id: platform.platform_id,
    platform_display_name: adapter.displayName,
    platform_confidence: platform.confidence,
  });
}

function handleApply(message: ContentMessage): ContentResponse<ApplyFillResult> {
  const instructions = message.instructions ?? [];
  if (instructions.length === 0) {
    return ok({
      filled: 0,
      failed: 0,
      skipped: 0,
      warnings: ["No instructions were provided; run 'Analyze with local profile' first."],
    });
  }
  return ok(applyFillInstructions(instructions));
}

function handleHighlight(message: ContentMessage): ContentResponse<{ marked: number }> {
  const mappings = message.mappings ?? [];
  // Custom controls are re-derived from the live page rather than trusted from the
  // message, so the "not supported" badge always reflects the current DOM.
  const unsupportedIds = detectFields(document)
    .fields.filter((field) => field.is_custom_control)
    .map((field) => field.field_id);
  return ok({ marked: highlightFields(mappings, unsupportedIds, document) });
}

function handleClear(): ContentResponse<{ cleared: number }> {
  return ok({ cleared: clearHighlights(document) });
}

function registerListener(): void {
  chrome.runtime.onMessage.addListener(
    (message: ContentMessage, _sender, sendResponse) => {
      try {
        switch (message?.type) {
          case MSG_PING:
            sendResponse(ok({ ready: true }));
            break;
          case MSG_DETECT_PLATFORM:
            sendResponse(handleDetectPlatform());
            break;
          case MSG_DETECT_FIELDS:
            sendResponse(handleDetect());
            break;
          case MSG_APPLY_FILL_INSTRUCTIONS:
            sendResponse(handleApply(message));
            break;
          case MSG_HIGHLIGHT_FIELDS:
            sendResponse(handleHighlight(message));
            break;
          case MSG_CLEAR_HIGHLIGHTS:
            sendResponse(handleClear());
            break;
          default:
            sendResponse(fail(`Unknown message type: ${String(message?.type)}`));
        }
      } catch (error) {
        sendResponse(fail(error));
      }
      // Every handler above responds synchronously, so the channel can close.
      return false;
    },
  );
}

const guarded = window as GuardedWindow;
if (!guarded[INJECTION_FLAG]) {
  guarded[INJECTION_FLAG] = true;
  registerListener();
}
