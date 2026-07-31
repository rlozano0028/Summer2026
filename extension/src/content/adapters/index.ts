/**
 * Adapter registry (Phase 7).
 *
 * Order matters: the first adapter whose signals match wins, so the specific ATS
 * adapters are tried before the generic fallback. `genericAdapter` is deliberately
 * excluded from `ATS_ADAPTERS` because it matches almost any form and would shadow
 * the others.
 *
 * Adapters are chosen from DOM signals, never from the URL. The URL decides whether
 * a page may be analyzed (that is the backend's job); the DOM decides how to read
 * it. Keeping the two apart is what lets a Greenhouse-shaped fixture on
 * `127.0.0.1` exercise the Greenhouse adapter while still being treated as a local
 * page.
 */

import type { PlatformAdapter, PlatformId } from "../../shared/platformTypes";
import { ashbyAdapter } from "./ashbyAdapter";
import { genericAdapter } from "./genericAdapter";
import { greenhouseAdapter } from "./greenhouseAdapter";
import { leverAdapter } from "./leverAdapter";
import { smartRecruitersAdapter } from "./smartRecruitersAdapter";
import { workdayAdapter } from "./workdayAdapter";

/** Vendor adapters, most distinctive signals first. */
export const ATS_ADAPTERS: readonly PlatformAdapter[] = [
  greenhouseAdapter,
  leverAdapter,
  ashbyAdapter,
  workdayAdapter,
  smartRecruitersAdapter,
];

export const ALL_ADAPTERS: readonly PlatformAdapter[] = [
  ...ATS_ADAPTERS,
  genericAdapter,
];

export function getAdapterById(platformId: string): PlatformAdapter {
  return (
    ALL_ADAPTERS.find((adapter) => adapter.platformId === platformId) ?? genericAdapter
  );
}

/**
 * Pick the adapter whose signals best match `doc`.
 *
 * Returns the generic adapter when nothing specific matches, which is the safe
 * default: it assumes the least about the page.
 */
export function selectAdapter(doc: Document): {
  adapter: PlatformAdapter;
  matched: string[];
  confidence: number;
} {
  let best: { adapter: PlatformAdapter; matched: string[]; confidence: number } | null =
    null;

  for (const adapter of ATS_ADAPTERS) {
    const { matched, confidence } = adapter.detectPlatformSignals(doc);
    if (matched.length === 0) continue;
    if (!best || confidence > best.confidence) {
      best = { adapter, matched, confidence };
    }
  }

  if (best) return best;

  const generic = genericAdapter.detectPlatformSignals(doc);
  return {
    adapter: genericAdapter,
    matched: generic.matched,
    confidence: generic.confidence,
  };
}

export {
  ashbyAdapter,
  genericAdapter,
  greenhouseAdapter,
  leverAdapter,
  smartRecruitersAdapter,
  workdayAdapter,
};

export type { PlatformAdapter, PlatformId };
