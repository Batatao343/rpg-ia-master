import { test, expect } from "./fixtures";

// SPEC-222 R9: cadastro exige idade mínima (D-D: 18) e mostra aceite com links legais.
const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });
const unauthenticated = { required: true, authenticated: false, lifecycle_available: true,
  email_confirmation_required: true, captcha: { required: false, site_key: null, provider: "turnstile" } };

test("SPEC-222 signup shows consent links and requires the age checkbox", async ({ page, backend }) => {
  backend.authenticated = false;
  await page.route("**/auth/config", route => route.fulfill(json(unauthenticated)));
  let signups = 0;
  let payload: Record<string, unknown> = {};
  await page.route("**/auth/signup", route => { signups += 1; payload = route.request().postDataJSON(); return route.fulfill(json({ authenticated: false,
    message: "Se o endereço puder receber mensagens, enviaremos as instruções." }, 202)); });
  await page.goto("/");
  const legal = page.getByRole("navigation", { name: "Documentos legais" });
  await expect(legal.getByRole("link", { name: "Privacidade" })).toHaveAttribute("href", "/privacidade/");
  await expect(legal.getByRole("link", { name: "Termos" })).toHaveAttribute("href", "/termos/");

  await page.getByRole("button", { name: "Criar uma conta local" }).click();
  const consent = page.getByTestId("signup-consent");
  await expect(consent).toContainText("provedores de IA");
  await expect(consent.getByRole("link", { name: "Termos" })).toHaveAttribute("href", "/termos/");
  await expect(consent.getByRole("link", { name: "Política de Privacidade" })).toHaveAttribute("href", "/privacidade/");
  await page.getByLabel("E-mail").fill("novo@example.test");
  await page.getByLabel("Senha", { exact: true }).fill("SenhaSegura123!");
  const submit = page.getByRole("button", { name: "Criar conta", exact: true });
  const age = page.getByLabel("Declaro ter 18 anos ou mais.");
  await expect(age).not.toBeChecked();
  await expect(submit).toBeDisabled();
  expect(signups).toBe(0);
  await age.check();
  await expect(submit).toBeEnabled();
  await submit.click();
  await expect(page.getByRole("status")).toContainText("Se o endereço puder receber mensagens");
  expect(signups).toBe(1);
  expect(payload.age_confirmed).toBe(true); // a API recusa (422) sem a declaração
});
