import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures";

const quoteId = "123e4567-e89b-42d3-a456-426614174000";

async function openGame(page: import("@playwright/test").Page) {
  await page.route("https://fonts.googleapis.com/**", route => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.goto("/");
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByRole("button", { name: "Cotar retrato", exact: true })).toBeVisible();
}

for (const width of [390, 1440]) {
  test(`SPEC-188 quote requires explicit confirmation at ${width}px`, async ({ page, backend }) => {
    await page.setViewportSize({ width, height: 850 });
    // React StrictMode may abort its first art-status poll during the dev remount.
    backend.allowFailure(/\/game\/game-a\/art\/123e4567-e89b-42d3-a456-426614174001$/);
    const quoted: Record<string, unknown>[] = [];
    const confirmed: Record<string, unknown>[] = [];
    await page.route("**/game/game-a/art/quote", route => {
      quoted.push(route.request().postDataJSON());
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        quote_id: quoteId, type: "player", credits_milli: "12500", pricing_version: "test-v1",
        expires_at: new Date(Date.now() + 300_000).toISOString(), reformulation: false,
      }) });
    });
    await page.route("**/game/game-a/art/confirm", route => {
      confirmed.push(route.request().postDataJSON());
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        status: "pending", generation_id: "123e4567-e89b-42d3-a456-426614174001", placeholder: true,
      }) });
    });
    await page.route("**/game/game-a/art/123e4567-e89b-42d3-a456-426614174001", route =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        status: "ready", placeholder: false, financial_status: "uncertain", credits_held: true,
        assets: [{ variant: "full",
          url: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E", width: 1, height: 1 }],
      }) }));
    await openGame(page);
    await page.getByRole("button", { name: "Cotar retrato" }).click();
    const dialog = page.getByRole("dialog", { name: "Encomendar imagem" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("Custo máximo: 12,5 Estilhas");
    expect(quoted).toEqual([{ image_type: "player", reformulation: false }]);
    expect(confirmed).toHaveLength(0);
    expect(backend.requests.filter(r => r.path.includes("/game/action"))).toHaveLength(0);
    const issues = (await new AxeBuilder({ page }).include(".image-quote-dialog").analyze())
      .violations.filter(v => ["serious", "critical"].includes(v.impact ?? ""));
    expect(issues).toEqual([]);
    await dialog.getByRole("button", { name: "Cancelar" }).click();
    await expect(dialog).not.toBeVisible();
    expect(confirmed).toHaveLength(0);
    await page.getByRole("button", { name: "Cotar retrato" }).click();
    await dialog.getByRole("button", { name: "Confirmar até 12,5 Estilhas" }).click();
    await expect(dialog).not.toBeVisible();
    expect(confirmed).toHaveLength(1);
    expect(confirmed[0]).toMatchObject({ quote_id: quoteId, confirmed: true });
    expect(confirmed[0].action_id).toMatch(/^[0-9a-f-]{36}$/);
    await expect(page.getByRole("img", { name: "Retrato do personagem" })).toBeVisible();
    await expect(page.getByText(/Resultado financeiro incerto/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test("SPEC-188 expired quote disables confirmation and never sends a paid request", async ({ page }) => {
  let confirms = 0;
  await page.route("**/game/game-a/art/quote", route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
    quote_id: quoteId, type: "player", credits_milli: "12500", pricing_version: "test-v1",
    expires_at: new Date(Date.now() - 1000).toISOString(), reformulation: false,
  }) }));
  await page.route("**/game/game-a/art/confirm", route => { confirms++; return route.fulfill({ status: 500, body: "unexpected" }); });
  await openGame(page);
  await page.getByRole("button", { name: "Cotar retrato" }).click();
  const dialog = page.getByRole("dialog", { name: "Encomendar imagem" });
  await expect(dialog.getByText(/Cotação expirada/)).toBeVisible();
  await expect(dialog.getByRole("button", { name: /Confirmar até/ })).toBeDisabled();
  expect(confirms).toBe(0);
});

test("SPEC-188 failed confirmation stays explicit and reuses its action ID", async ({ page, backend }) => {
  backend.allowConsole(/402/);
  const attempts: Record<string, unknown>[] = [];
  await page.route("**/game/game-a/art/quote", route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
    quote_id: quoteId, type: "player", credits_milli: "12500", pricing_version: "test-v1",
    expires_at: new Date(Date.now() + 300_000).toISOString(), reformulation: false,
  }) }));
  await page.route("**/game/game-a/art/confirm", route => {
    attempts.push(route.request().postDataJSON());
    return route.fulfill({ status: attempts.length === 1 ? 402 : 200, contentType: "application/json",
      body: JSON.stringify(attempts.length === 1
        ? { detail: "image_insufficient_shards" }
        : { status: "pending", generation_id: "123e4567-e89b-42d3-a456-426614174001", placeholder: true }) });
  });
  backend.allowFailure(/\/game\/game-a\/art\/123e4567-e89b-42d3-a456-426614174001$/);
  await openGame(page);
  await page.getByRole("button", { name: "Cotar retrato" }).click();
  const dialog = page.getByRole("dialog", { name: "Encomendar imagem" });
  const confirm = dialog.getByRole("button", { name: "Confirmar até 12,5 Estilhas" });
  await confirm.click();
  await expect(dialog.getByRole("alert")).toContainText("Não foi possível confirmar");
  expect(attempts).toHaveLength(1);
  await confirm.click();
  await expect(dialog).not.toBeVisible();
  expect(attempts).toHaveLength(2);
  expect(attempts[1].action_id).toBe(attempts[0].action_id);
  expect(attempts[1]).toMatchObject({ quote_id: quoteId, confirmed: true });
});

test("SPEC-188 changing campaign clears pending quote busy state and ignores late response", async ({ page }) => {
  let releaseOld!: () => void;
  const oldGate = new Promise<void>(resolve => { releaseOld = resolve; });
  await page.route("**/game/game-a/art/quote", async route => {
    await oldGate;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      quote_id: quoteId, type: "player", credits_milli: "12500", pricing_version: "test-v1",
      expires_at: new Date(Date.now() + 300_000).toISOString(), reformulation: false,
    }) });
  });
  await page.route("**/game/game-created/art/quote", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({
      quote_id: "123e4567-e89b-42d3-a456-426614174002", type: "player", credits_milli: "8000",
      pricing_version: "test-v1", expires_at: new Date(Date.now() + 300_000).toISOString(), reformulation: false,
    }),
  }));
  await openGame(page);
  await page.getByRole("button", { name: "Cotar retrato" }).click();
  await expect(page.getByRole("button", { name: "Cotar retrato" })).toBeDisabled();
  await page.getByRole("button", { name: "Nova" }).click();
  await page.getByRole("button", { name: /Origem/ }).click();
  await page.getByRole("button", { name: "Humano" }).click();
  await page.getByRole("button", { name: /Vocação/ }).click();
  await page.getByRole("button", { name: "Devoto do Abismo" }).click();
  await page.getByRole("button", { name: /Região/ }).click();
  await page.getByRole("button", { name: /Porto Cinzento/ }).click();
  await page.getByRole("button", { name: /Identidade/ }).click();
  await page.getByLabel("Nome do herói").fill("Mira");
  await page.getByRole("button", { name: "Tecer o prólogo" }).click();
  await page.getByRole("button", { name: "Começar a jornada" }).click();
  await expect(page.getByRole("button", { name: "Cotar retrato" })).toBeEnabled();
  releaseOld();
  await page.getByRole("button", { name: "Cotar retrato" }).click();
  const dialog = page.getByRole("dialog", { name: "Encomendar imagem" });
  await expect(dialog).toContainText("8 Estilhas");
  await expect(dialog).not.toContainText("12,5 Estilhas");
});

for (const type of ["npc", "scene"] as const) {
  test(`SPEC-188 ${type} generation remains visible with held balance after reload`, async ({ page, backend }) => {
    const generationId = type === "npc" ? "123e4567-e89b-42d3-a456-426614174011" : "123e4567-e89b-42d3-a456-426614174012";
    const offerId = type === "npc" ? "123e4567-e89b-42d3-a456-426614174021" : "123e4567-e89b-42d3-a456-426614174022";
    const game = backend.states.get("game-a")!;
    game.art_offers = [{ offer_id: offerId, type }];
    backend.allowFailure(new RegExp(`/game/game-a/art/${generationId}$`));
    const confirms: Record<string, unknown>[] = [];
    await page.route("**/game/game-a/art/quote", route => {
      expect(route.request().postDataJSON()).toEqual({ image_type: type, reformulation: false, offer_id: offerId });
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        quote_id: quoteId, type, credits_milli: "12500", pricing_version: "test-v1",
        expires_at: new Date(Date.now() + 300_000).toISOString(), reformulation: false,
      }) });
    });
    await page.route("**/game/game-a/art/confirm", route => {
      confirms.push(route.request().postDataJSON());
      game.art_offers = [];
      game.art_generations = [{ generation_id: generationId, type, subject_id: "borin" }];
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        status: "pending", generation_id: generationId, type, placeholder: true,
        art_offers: game.art_offers, art_generations: game.art_generations,
      }) });
    });
    await page.route(`**/game/game-a/art/${generationId}`, route =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        status: "reconcile_required", placeholder: true, financial_status: "uncertain",
        credits_held: true, assets: [],
      }) }));
    await openGame(page);
    const offerLabel = type === "npc" ? "Cotar retrato de NPC" : "Cotar cena épica";
    await page.getByRole("button", { name: offerLabel }).click();
    const dialog = page.getByRole("dialog", { name: "Encomendar imagem" });
    await dialog.getByRole("button", { name: "Confirmar até 12,5 Estilhas" }).click();
    const card = page.getByRole("region", { name: type === "npc" ? "Retrato de NPC" : "Cena épica" });
    await expect(card).toContainText("Saldo retido para conferência");
    await expect(page.getByRole("button", { name: offerLabel })).toHaveCount(0);
    await page.reload();
    await page.getByRole("button", { name: /^Ayla/ }).click();
    await expect(card).toContainText("Saldo retido para conferência");
    await expect(page.getByRole("button", { name: offerLabel })).toHaveCount(0);
    expect(confirms).toHaveLength(1);
  });
}
