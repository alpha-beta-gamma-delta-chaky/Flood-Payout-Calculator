import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// `npm run dev` proxies the API to the FastAPI service started with: uvicorn app.main:app --port 8000
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://127.0.0.1:8000", "/health": "http://127.0.0.1:8000" } },
  test: { environment: "jsdom", setupFiles: "./src/test-setup.ts", globals: true },
});
