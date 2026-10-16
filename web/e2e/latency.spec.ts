import { writeFileSync, mkdirSync } from "node:fs";
import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

// SPEC-200 R9: marcas `performance` por turno (submit < ack <= first_phase <= ttfmc <= ttlt <= state).
// A API e a determinística das fixtures; o smoke com latência injetada em tempo real
// (scripts/latency_baseline.py serve) fica documentado em docs/spec200/README.md.

async function openGame(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
}

type Measure = { name: string; startTime: number; duration: number };

const turnMeasures = (page: Page) =>
  page.evaluate<Measure[]>(() => performance.getEntriesByType("measure")
    .filter((e) => e.name.startsWith("rpg:turn:"))
    .map((e) => ({ name: e.name, startTime: e.startTime, duration: e.duration })));

for (const width of [390, 1440]) {
  test(`SPEC-200 performance marks per turn @${width}`, async ({ page, backend }) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await openGame(page);
    await page.getByPlaceholder(/O que você faz/).fill("Observo o porto com atenção");
    await page.getByRole("button", { name: "Agir" }).click();
    await expect(page.getByText("O mundo responde a: Observo o porto com atenção").first()).toBeVisible();

    await expect.poll(async () => (await turnMeasures(page)).some((m) => m.name.endsWith(":state:ms"))).toBe(true);
    const measures = await turnMeasures(page);
    expect(measures.length).toBeGreaterThanOrEqual(5);
    const byMark = (mark: string) => measures.find((m) => m.name.endsWith(`:${mark}:ms`));
    const actionIds = new Set(measures.map((m) => m.name.split(":")[2]));
    expect(actionIds.size).toBe(1);                     // um action_id por turno
    const order = ["ack", "first_phase", "ttfmc", "ttlt", "state"].map((m) => byMark(m));
    for (const entry of order) expect(entry, "marca ausente").toBeTruthy();
    const durations = order.map((m) => m!.duration);
    for (let i = 1; i < durations.length; i++) expect(durations[i]).toBeGreaterThanOrEqual(durations[i - 1]);
    // TTFMC vem depois do último `phase` (aqui: o primeiro phase da fixture).
    expect(byMark("ttfmc")!.duration).toBeGreaterThanOrEqual(byMark("first_phase")!.duration);
    // Beacon desligado por default: nenhuma chamada ao endpoint de telemetria.
    expect(backend.requests.some((r) => r.path.startsWith("/telemetry"))).toBe(false);

    if (process.env.RPG_SPEC200_EVIDENCE) {
      mkdirSync("../docs/spec200", { recursive: true });
      writeFileSync(`../docs/spec200/performance-measures-${width}.json`, JSON.stringify(measures, null, 2) + "\n");
    }
  });
}
