import { defineConfig } from "vitest/config";

// Separate from vite.config.ts on purpose: that file describes how the popup is
// *built* (a single HTML entry, no test globals), and mixing a `test` block into it
// would mean every production build carries test configuration.
//
// jsdom is required rather than optional: the modules under test here are the safety
// gates - URL rules, platform detection, the filler's refusals, the highlighter - and
// all but the first need a DOM to be tested at all.
export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["src/**/*.spec.ts"],
    globals: true,
    restoreMocks: true,
  },
});
