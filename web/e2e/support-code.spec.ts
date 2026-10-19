import { test, expect } from "./fixtures";

// SPEC-243: erro de login mostra mensagem amigavel + codigo de suporte, nunca o codigo cru.
const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  ({ status, contentType: "application/json", body: JSON.stringify(body), headers });
const unauthenticated = { required: true, authenticated: false, lifecycle_available: true,
  email_confirmation_required: true, captcha: { required: false, site_key: null, provider: "turnstile" } };

test("SPEC-243 invalid login shows a friendly message and a support code", async ({ page, backend }) => {
  backend.authenticated = false;
  backend.allowConsole(/status of 401/);
  await page.route("**/auth/config", route => route.fulfill(json(unauthenticated)));
  await page.route("**/auth/login", route => route.fulfill(json(
    { detail: "credentials_invalid", code: "credentials_invalid", request_id: "e2e0req1-aaaa-bbbb-cccc-ddddeeeeffff" },
    401, { "X-Request-ID": "e2e0req1-aaaa-bbbb-cccc-ddddeeeeffff" })));
  await page.goto("/");
  await page.getByLabel("E-mail").fill("alguem@example.test");
  await page.getByLabel("Senha", { exact: true }).fill("SenhaErrada123!");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  const alert = page.getByRole("alert").filter({ hasText: "E-mail ou senha incorretos." });
  await expect(alert).toBeVisible();
  await expect(alert).toContainText("Código de suporte: e2e0req1-aaaa-bbbb-cccc-ddddeeeeffff");
  await expect(alert).not.toContainText("credentials_invalid");
  await expect(page.locator("body")).not.toContainText(/\b[a-z]+_[a-z_]+\b(?=\s*$)/m);
  await alert.getByRole("button", { name: "Copiar código de suporte" }).focus();
});
