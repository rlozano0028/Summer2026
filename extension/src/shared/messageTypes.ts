/**
 * Typed envelopes for popup <-> content script messages.
 *
 * Phase 6 used a loose `ContentMessage { type: string; ... }` shape, which is fine
 * for four messages but stops being fine once the payloads differ. These
 * discriminated unions let TypeScript catch a handler that reads `instructions`
 * from a message that does not carry them.
 *
 * The message *name* constants stay in constants.ts, where the rest of the shared
 * strings live; this file only describes the shapes.
 */

import {
  MSG_APPLY_FILL_INSTRUCTIONS,
  MSG_CLEAR_HIGHLIGHTS,
  MSG_DETECT_FIELDS,
  MSG_DETECT_PLATFORM,
  MSG_HIGHLIGHT_FIELDS,
  MSG_PING,
} from "./constants";
import type { DetectPlatformResult } from "./platformTypes";
import type {
  ApplyFillResult,
  DetectFieldsResult,
  ExtensionFillInstruction,
  FieldMapping,
} from "./types";

export interface PingMessage {
  type: typeof MSG_PING;
}

export interface DetectPlatformMessage {
  type: typeof MSG_DETECT_PLATFORM;
}

export interface DetectFieldsMessage {
  type: typeof MSG_DETECT_FIELDS;
}

/**
 * Apply instructions. `instructions` may include values for safe fill decisions,
 * so this message is passed straight from the analyze response to the content
 * script and then dropped. It is never stored.
 */
export interface ApplyFillMessage {
  type: typeof MSG_APPLY_FILL_INSTRUCTIONS;
  instructions: ExtensionFillInstruction[];
}

export interface HighlightMessage {
  type: typeof MSG_HIGHLIGHT_FIELDS;
  mappings: FieldMapping[];
}

export interface ClearHighlightsMessage {
  type: typeof MSG_CLEAR_HIGHLIGHTS;
}

export type PopupToContentMessage =
  | PingMessage
  | DetectPlatformMessage
  | DetectFieldsMessage
  | ApplyFillMessage
  | HighlightMessage
  | ClearHighlightsMessage;

/** Maps each message to what the content script sends back. */
export interface ContentResponseMap {
  [MSG_PING]: { ok: true };
  [MSG_DETECT_PLATFORM]: DetectPlatformResult;
  [MSG_DETECT_FIELDS]: DetectFieldsResult;
  [MSG_APPLY_FILL_INSTRUCTIONS]: ApplyFillResult;
  [MSG_HIGHLIGHT_FIELDS]: { highlighted: number };
  [MSG_CLEAR_HIGHLIGHTS]: { cleared: number };
}
