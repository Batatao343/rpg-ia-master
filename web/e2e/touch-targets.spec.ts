// SPEC-321 R7: com ponteiro grosso (`pointer: coarse`), todo controle visível da tela de jogo mede ≥ 44×44 px
// na tela de jogo e nas superfícies Personagem, Codex, Combate e Mapa.
import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

async function openGame(page: Page) {
  await page.route("https://fonts.googleapis.com/**", (route) => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).tap();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
}

const bar = (page: Page) => page.getByRole("navigation", { name: "Superfícies" });

/** Controles visíveis e interativos da tela de jogo que medem menos de 44 px em alguma dimensão. */
async function undersized(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const out: string[] = [];
    const nodes = document.querySelectorAll<HTMLElement>(".play button, .play [role=button], .play select, .play a[href], .playmenu button");
    for (const el of nodes) {
      if (el.closest("[hidden]") || el.closest(".sr-only")) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === "hidden" || cs.display === "none" || cs.pointerEvents === "none") continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      if (r.width < 43.5 || r.height < 43.5) {
        out.push(`${el.tagName.toLowerCase()}.${el.className.toString().split(" ")[0]} "${(el.getAttribute("aria-label") || el.textContent || "").trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
      }
    }
    return out;
  });
}

test("todo controle da tela de jogo tem ≥ 44×44 px (ponteiro grosso)", async ({ page, backend }) => {
  backend.armCombat("game-a", [["e1", "Saqueador"], ["e2", "Bandoleiro"]]);
  await openGame(page);
  const seen: Record<string, string[]> = {};
  for (const name of ["Crônica", "Personagem", "Codex", "Combate", "Mapa"]) {
    await bar(page).getByRole("button", { name, exact: true }).tap();
    await expect(bar(page).getByRole("button", { name, exact: true })).toHaveAttribute("aria-current", "page");
    await page.waitForTimeout(250); // abas montam na 1ª visita
    seen[name] = await undersized(page);
  }
  expect(seen).toEqual({ Crônica: [], Personagem: [], Codex: [], Combate: [], Mapa: [] });
});
