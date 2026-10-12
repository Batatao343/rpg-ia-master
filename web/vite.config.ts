import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Em dev, o app roda no Vite (5173) e fala com a API FastAPI (8000) via proxy.
// Em produção, `npm run build` gera web/dist e o FastAPI serve estático na raiz.
const API = "http://localhost:8000";

export default defineConfig({
  base: "/",
  plugins: [react()],
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
