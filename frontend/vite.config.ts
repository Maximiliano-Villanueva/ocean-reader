import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Single pdfjs-dist instance — must match react-pdf's worker and API version.
    dedupe: ["pdfjs-dist"],
  },
  optimizeDeps: {
    include: ["pdfjs-dist", "react-pdf"],
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
