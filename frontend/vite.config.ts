import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the backend runs on :8765; in production nginx proxies /api.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: { "/api": { target: process.env.API_URL ?? "http://127.0.0.1:8765", changeOrigin: true } },
  },
});
