/**
 * Content script message handler (Phase 6).
 *
 * This script is injected on the loopback origins listed in the manifest, but it
 * does nothing on load beyond registering a message listener. Every action -
 * detecting, highlighting, filling, clearing - happens only in response to a
 * message the user triggered by clicking a button in the popup.
 *
 * It makes no backend calls of its own. The popup orchestrates
 * popup -> backend and popup -> content script so that page context and network
 * access stay separated.
 */

import {
  MSG_APPLY_FILL_INSTRUCTIONS,
  MSG_CLEAR_HIGHLIGHTS,
  MSG_DETECT_FIELDS,
  MSG_HIGHLIGHT_FIELDS,
  MSG_PING,
} from "../shared/constants";
import type {
  ApplyFillResult,
  ContentMessage,
  ContentResponse,
  DetectFieldsResult,
} from "../shared/types";
import { detectFields } from "./fieldDetector";
import { clearHighlights, highlightFields } from "./pageHighlighter";
import { applyFillInstructions } from "./safeFiller";

function ok<T>(data: T): ContentResponse<T> {
  return { ok: true, data };
}

function fail(error: unknown): ContentResponse<never> {
  return { ok: false, error: error instanceof Error ? error.message : String(error) };
}

function handleDetect(): ContentResponse<DetectFieldsResult> {
  const { fields, warnings } = detectFields();
  return ok({
    page_url: window.location.href,
    page_title: document.title,
    fields,
    warnings,
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
  return ok({ marked: highlightFields(message.mappings ?? []) });
}

function handleClear(): ContentResponse<{ cleared: number }> {
  return ok({ cleared: clearHighlights() });
}

chrome.runtime.onMessage.addListener((message: ContentMessage, _sender, sendResponse) => {
  try {
    switch (message?.type) {
      case MSG_PING:
        sendResponse(ok({ ready: true }));
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
});
