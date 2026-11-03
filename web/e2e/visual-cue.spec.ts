// SPEC-379 R6 (Etapa 4): substitui test_frontend_contract_contains_visual_flow (tests/test_visual_assets.py)
// e tests/test_frontend_accessibility_contracts.py, que liam substrings de App.tsx/CreateScreen/StoryLog/
// ChatSurface/SceneArtwork. Aqui o comportamento: arte de cena, cue de NPC e arte de raça/classe.
import { test, expect } from "./fixtures";
import type { Page } from "@playwright/test";

const ART = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='640' height='360'%3E%3Crect width='100%25' height='100%25' fill='%23120f18'/%3E%3C/svg%3E";
const asset = (id: string, subject: string, alt: string) => ({
  asset_id: id, subject_type: "npc" as const, subject_id: subject, title: alt, alt, placeholder_color: "#120f18",
  variants: { thumbnail: { url: ART, width: 320, height: 180, bytes: 1, sha256: "a" }, display: { url: ART, width: 640, height: 360, bytes: 1, sha256: "b" } },
});

async function openGame(page: Page) {
  await page.goto("/");
  await page.getByRole("heading", { name: "Continuar jornada" }).waitFor();
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByText("Ayla", { exact: true }).first()).toBeVisible();
}

test("SPEC-379 R6: arte de cena no chat tem alt do asset e o contêiner não leva aria-label", async ({ page }) => {
  await openGame(page);
  const scene = page.locator(".scene-art");
  await expect(scene.getByRole("img", { name: "Porto Cinzento sob névoa" })).toHaveAttribute("alt", "Porto Cinzento sob névoa");
  await expect(scene).not.toHaveAttribute("aria-label", /.*/);
});

test("SPEC-379 R6: visual.cue da ação aparece como arte na narração", async ({ page, backend }) => {
  // actionResult clona o estado salvo; o cue vai na resposta do turno (App repassa r.visual?.cue).
  backend.states.get("game-a")!.visual.cue = { kind: "npc_first_appearance", subject_id: "borin", subject_name: "Borin",
    caption: "O barqueiro", fallback: false, asset: asset("npc-borin", "borin", "Retrato de Borin") };
  await openGame(page);
  await page.getByPlaceholder(/O que você faz/).fill("Olho em volta");
  await page.getByRole("button", { name: "Agir" }).click();
  await expect(page.locator(".msg__visual").getByRole("img", { name: "Retrato de Borin" })).toBeVisible();
});

test("SPEC-379 R6: criação mostra a arte de raça e de classe vindas de /data/options", async ({ page, backend }) => {
  backend.saves = [];
  await page.route("**/data/options", async (route) => {
    await route.fulfill({ json: {
      races: ["Humano", "Elfo"], classes: ["Devoto do Abismo", "Médico do Véu"], regions: ["Porto Cinzento", "Brumalta"],
      races_full: [{ id: "humano", name: "Humano", desc: "Adaptável", traits: [] }],
      visuals: { races: { humano: asset("race-humano", "humano", "Arte da raça Humano") },
        classes: { "Devoto do Abismo": asset("class-devoto", "devoto", "Arte da classe Devoto") } },
    } });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Continuar", exact: true }).click();
  await expect(page.getByRole("img", { name: "Arte da raça Humano" })).toBeVisible();
  await page.getByRole("button", { name: "Humano", exact: true }).click();
  await page.getByRole("button", { name: "Continuar", exact: true }).click();
  await page.getByRole("button", { name: "Devoto do Abismo", exact: true }).first().click();
  await expect(page.getByRole("img", { name: "Arte da classe Devoto" }).first()).toBeVisible();
});
