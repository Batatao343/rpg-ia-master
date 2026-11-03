// SPEC-379 R6 (Etapa 4): substitui tests/test_frontend_auth_bootstrap.py, que lia a posição de
// três strings em App.tsx. Aqui o comportamento: sem sessão, o app não chama /game/saves.
import { test, expect } from "./fixtures";

test("SPEC-379 R6: zero /game/saves antes do login e pelo menos um depois", async ({ page, backend }) => {
  backend.authenticated = false;
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Retorne à fogueira" })).toBeVisible();
  expect(backend.requests.filter((r) => r.path === "/game/saves")).toEqual([]);
  expect(backend.protectedBeforeAuth).toBe(0);

  await page.getByLabel("E-mail").fill("ayla@example.test");
  await page.getByLabel("Senha").fill("segredo-valoria");
  await page.getByRole("button", { name: "Criar uma conta local" }).click();
  await page.getByLabel("Declaro ter 18 anos ou mais.").check();
  await page.getByRole("button", { name: "Criar conta" }).click();
  await expect(page.getByRole("heading", { name: "Continuar jornada" })).toBeVisible();
  expect(backend.requests.filter((r) => r.path === "/game/saves").length).toBeGreaterThanOrEqual(1);
});
