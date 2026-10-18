import { test, expect } from "./fixtures";

// Regressão: o "cartão inteiro clicável" de SPEC-208 (`.card__select::after`,
// absoluto com inset 0) vazava para os botões de ampliar arte fora de um
// `.card`. Sem ancestral posicionado, a camada cobria o workspace inteiro e
// roubava cliques dos controles (ex.: "Chat" em 390px abria o retrato).
for (const width of [390, 1440]) {
  test(`retrato gerado não captura cliques fora da imagem @${width}`, async ({ page, backend }) => {
    await page.setViewportSize({ width, height: 900 });
    (backend.states.get("game-a") as unknown as Record<string, unknown>).portrait_generation_id = "portrait-1";
    // StrictMode cancela a primeira consulta de arte no remount de desenvolvimento.
    backend.allowFailure(/\/game\/game-a\/art\/portrait-1$/);
    await page.goto("/");
    await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
    await page.getByRole("button", { name: /^Ayla/ }).click();
    await page.getByRole("button", { name: "☰ Ficha" }).click();
    const enlarge = page.getByRole("button", { name: "Ampliar retrato do personagem" });
    await expect(enlarge).toBeVisible();

    // Fora do botão, o ponto pertence a outro elemento (a camada não vaza).
    const hitsOutside = await enlarge.evaluate((el) => {
      const box = el.getBoundingClientRect();
      const probes: [number, number][] = [[box.left + box.width / 2, box.top - 12], [box.left + box.width / 2, box.bottom + 12]];
      return probes.filter(([x, y]) => y > 0 && y < innerHeight && el.contains(document.elementFromPoint(x, y))).length;
    });
    expect(hitsOutside).toBe(0);

    if (width < 900) {
      // SPEC-216: a barra "Superfícies" substitui o grupo "Modo de exibição".
      const chat = page.getByRole("navigation", { name: "Superfícies" }).getByRole("button", { name: "Chat", exact: true });
      await chat.click({ timeout: 3_000 });
      await expect(chat).toHaveAttribute("aria-current", "page");
    }
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });
}
