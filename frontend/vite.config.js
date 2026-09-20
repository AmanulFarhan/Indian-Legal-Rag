import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/static/",
  plugins: [react(), tailwindcss()],
  build: { outDir: "dist", emptyOutDir: true, sourcemap: true },
  server: {
    port: 5173,
    proxy: {
      "/ask": "http://127.0.0.1:8000",
      "/analyze-document": "http://127.0.0.1:8000",
      "/api": "http://127.0.0.1:8000",
    },
  },
});
