import { defineConfig } from "vite";

// Vite builds the popup only. The content script and service worker are bundled
// separately as IIFE by scripts/build-scripts.mjs, because Manifest V3 will not
// load a content script that contains bare ES module imports.
//
// As in ../frontend, we deliberately avoid @vitejs/plugin-react: esbuild
// transpiles .tsx via the "automatic" JSX runtime, so the build works with just
// the packages listed in package.json. Trade-off: no React Fast Refresh.
export default defineConfig({
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: "popup.html",
      },
    },
  },
  esbuild: {
    jsx: "automatic",
  },
});
