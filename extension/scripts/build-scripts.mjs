/**
 * Bundle the content script and service worker for Manifest V3.
 *
 * These two entry points cannot be built by the popup's Vite pass: MV3 refuses to
 * run a content script containing bare ES module imports, and the service worker
 * is simplest as a self-contained file. esbuild produces one IIFE bundle each,
 * with no imports left to resolve at load time.
 *
 * Runs after `vite build`, which owns (and empties) dist/.
 */

import { build } from "esbuild";
import { fileURLToPath } from "node:url";
import path from "node:path";

const extensionRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** @type {{entry: string, outfile: string}[]} */
const targets = [
  {
    entry: "src/content/contentScript.ts",
    outfile: "dist/content/contentScript.js",
  },
  {
    entry: "src/background/serviceWorker.ts",
    outfile: "dist/background/serviceWorker.js",
  },
];

for (const { entry, outfile } of targets) {
  await build({
    absWorkingDir: extensionRoot,
    entryPoints: [entry],
    outfile,
    bundle: true,
    format: "iife",
    platform: "browser",
    target: "chrome114",
    // Keep output readable so the behaviour can be audited in DevTools.
    minify: false,
    sourcemap: false,
    legalComments: "none",
  });
  console.log(`built ${entry} -> ${outfile}`);
}
