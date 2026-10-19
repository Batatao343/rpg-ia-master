import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { computeBuildId } from "./scripts/buildId.mjs";

// Em dev, o app roda no Vite (5173) e fala com a API FastAPI (8000) via proxy.
// Em produção, `npm run build` gera web/dist e o FastAPI serve estático na raiz.
const API = "http://localhost:8000";

export default defineConfig({
  base: "/",
  plugins: [react()],
  // SPEC-261 R1: build id (sha curto + timestamp) para X-RPG-Build e a tela de conta.
  define: { __RPG_BUILD__: JSON.stringify(computeBuildId()) },
  server: {
    port: 5173,
    proxy: {
      "/data": API,
      "/game": API,
      "/account": API,
      "/health": API,
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
