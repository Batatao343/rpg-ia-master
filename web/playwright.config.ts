import { defineConfig, devices } from "@playwright/test";
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function localChromium(): string | undefined {
  if (process.env.RPG_BROWSER_EXECUTABLE) return process.env.RPG_BROWSER_EXECUTABLE;
  const root = join(homedir(), ".agent-browser", "browsers");
  if (!existsSync(root)) return undefined;
  const candidates = readdirSync(root)
    .filter((name) => name.startsWith("chrome-"))
    .sort()
    .reverse()
    .map((name) => join(root, name, process.platform === "win32" ? "chrome.exe" : "chrome"));
  return candidates.find(existsSync);
}

export default defineConfig({
  testDir: "./e2e",
  // Execuções concorrentes/em loop isolam artefatos por RPG_PW_OUTPUT_DIR (padrão inalterado).
  outputDir: process.env.RPG_PW_OUTPUT_DIR ?? "test-results",
  fullyParallel: false,
  timeout: 30_000,
  expect: { timeout: 8_000 },
  // Retry poderia transformar uma falha em sucesso silencioso no required gate.
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "test-results/results.json" }]],
  use: {
    baseURL: "http://127.0.0.1:4173",
    browserName: "chromium",
    reducedMotion: "reduce",
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    launchOptions: { executablePath: localChromium() },
  },
  webServer: {
    // RPG_E2E_SERVER=preview serve web/dist (medição de performance contra o build real).
    command: process.env.RPG_E2E_SERVER === "preview"
      ? "node ./node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4173"
      : "node ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    { name: "chromium", testIgnore: /mobile-single-pane\.spec\.ts/, use: { ...devices["Desktop Chrome"] } },
    // SPEC-216: jornadas M01-M07, uma vez por viewport mobile (toque, sem hover); chromium empacotado.
    ...[{ name: "mobile-320", width: 320, height: 568 }, { name: "mobile-390", width: 390, height: 844 }].map((v) => ({
      name: v.name, testMatch: /mobile-single-pane\.spec\.ts/,
      use: { ...devices["Pixel 5"], actionTimeout: 8_000, viewport: { width: v.width, height: v.height }, reducedMotion: "reduce" as const },
    })),
    // SPEC-208: só os efeitos precisam de movimento ligado; o resto da suíte segue em `reduce`.
    { name: "chromium-motion", testMatch: /effects\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], reducedMotion: "no-preference",
        // evidência de aceite (smoke §6): vídeo + trace só quando pedido
        ...(process.env.RPG_EFFECTS_EVIDENCE ? { video: { mode: "on" as const, size: { width: 960, height: 600 } }, trace: "on" as const } : {}) } },
  ],
});
