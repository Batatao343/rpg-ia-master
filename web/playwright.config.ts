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
    command: "node ./node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
