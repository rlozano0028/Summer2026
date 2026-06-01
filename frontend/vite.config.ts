import { defineConfig } from "vite";

// Minimal Vite config. We intentionally do NOT depend on @vitejs/plugin-react
// so that `npm run build` works offline with the packages already installed;
// Vite/esbuild transpiles .tsx using the tsconfig "jsx": "react-jsx" setting.
// (Trade-off: no React Fast Refresh in dev - the page does a full reload on
// change. Add @vitejs/plugin-react later if you want HMR.)
export default defineConfig({
  server: {
    port: 5173,
  },
  esbuild: {
    jsx: "automatic",
  },
});
