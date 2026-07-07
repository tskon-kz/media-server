import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// Dev: the SPA runs on the Mac (hot reload) and the backend API lives on the
// dev server. Point VITE_DEV_API_BASE at it, e.g.
//   VITE_DEV_API_BASE=http://<dev-tailscale-host>:8081
// (the dev server must run with WEBAPP_DEV_MODE=1 + port 8081 published — see
// docker-compose.dev.yml). Prod serves the built SPA from the same origin as
// /api, so no proxy is needed there.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const apiBase = env.VITE_DEV_API_BASE || "http://localhost:8081";
  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: {
      proxy: {
        "/api": { target: apiBase, changeOrigin: true },
      },
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
    },
  };
});
