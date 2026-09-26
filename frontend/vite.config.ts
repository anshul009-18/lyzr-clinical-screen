import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
      proxy: {
      "/ingest": "http://localhost:8000",
      "/screen": "http://localhost:8000",
      "/audit": "http://localhost:8000",
      "/aims": "http://localhost:8000",
      "/hitl": "http://localhost:8000",
    },
  },
});
