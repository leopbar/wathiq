import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";

const apiTarget = process.env.VITE_API_PROXY ?? "http://api:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Inside Compose the app is reached as http://web:5173 (Playwright, other containers).
    // Vite rejects unknown Host headers with 403, so the service name must be allowed.
    allowedHosts: ["web", "localhost", "127.0.0.1"],
    // The project lives on a Windows drive, so inotify events do not cross the
    // Docker boundary reliably. Polling keeps hot reload working.
    watch: { usePolling: true, interval: 400 },
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        // Server-Sent Events must not be buffered.
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes) => {
            if (proxyRes.headers["content-type"]?.includes("text/event-stream")) {
              proxyRes.headers["cache-control"] = "no-cache, no-transform";
            }
          });
        },
      },
      "/healthz": { target: apiTarget, changeOrigin: true },
    },
  },
  preview: { host: "0.0.0.0", port: 5173, strictPort: true },
  build: { outDir: "dist", sourcemap: false, chunkSizeWarningLimit: 1200 },
});
