import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures";

const json = (body: unknown, status = 200) => ({ status, contentType: "application/json", body: JSON.stringify(body) });
const unauthenticated = { required: true, authenticated: false, lifecycle_available: true,
  email_confirmation_required: true, captcha: { required: false, site_key: null, provider: "turnstile" } };

test("SPEC-190 signup awaits verification and email requests disclose no account existence", async ({ page, backend }) => {
  backend.authenticated = false;
  await page.route("**/auth/config", route => route.fulfill(json(unauthenticated)));
  await page.route("**/auth/signup", route => route.fulfill(json({ authenticated: false,
    message: "Se o endereço puder receber mensagens, enviaremos as instruções." }, 202)));
  await page.route("**/auth/reset/request", route => route.fulfill(json({ message: "Instruções enviadas." }, 202)));
  await page.route("**/auth/verify/request", route => route.fulfill(json({ message: "Instruções enviadas." }, 202)));
  await page.goto("/");
  await page.getByRole("button", { name: "Criar uma conta local" }).click();
  await page.getByLabel("E-mail").fill("novo@example.test");
  await page.getByLabel("Senha", { exact: true }).fill("SenhaSegura123!");
  await page.getByLabel("Declaro ter 18 anos ou mais.").check(); // SPEC-222 R9
  await page.getByRole("button", { name: "Criar conta", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Se o endereço puder receber mensagens");
  expect(backend.protectedBeforeAuth).toBe(0);
  expect(backend.requests.some(request => request.path === "/game/saves")).toBe(false);

  await page.getByRole("button", { name: "Já tenho uma conta" }).click();
  await page.getByRole("button", { name: "Esqueci minha senha" }).click();
  await page.getByLabel("E-mail").fill("desconhecido@example.test");
  await page.getByRole("button", { name: "Enviar recuperação" }).click();
  await expect(page.getByRole("status")).toContainText("Se o endereço puder receber mensagens");
  await page.getByRole("button", { name: "Voltar para entrar" }).click();
  await page.getByRole("button", { name: "Reenviar confirmação de e-mail" }).click();
  await page.getByLabel("E-mail").fill("desconhecido@example.test");
  await page.getByRole("button", { name: "Enviar confirmação" }).click();
  await expect(page.getByRole("status")).toContainText("Se o endereço puder receber mensagens");
});

test("SPEC-190 recovery token stays in fragment and is removed before API call", async ({ page, backend }) => {
  backend.authenticated = false;
  await page.route("**/auth/config", route => route.fulfill(json(unauthenticated)));
  let confirmed: unknown;
  await page.route("**/auth/reset/confirm", route => {
    confirmed = route.request().postDataJSON();
    return route.fulfill(json({ authenticated: false, message: "Senha atualizada." }));
  });
  await page.goto("/#auth_action=recovery&token_hash=private-reset-token");
  await expect(page).toHaveURL("http://127.0.0.1:4173/");
  await page.getByLabel("Nova senha", { exact: true }).fill("NovaSenhaSegura123!");
  await page.getByLabel("Repita a nova senha").fill("NovaSenhaSegura123!");
  await page.getByRole("button", { name: "Atualizar senha" }).click();
  await expect(page.getByRole("status")).toContainText("Senha atualizada");
  expect(confirmed).toEqual({ token_hash: "private-reset-token", new_password: "NovaSenhaSegura123!" });
  expect(backend.requests.some(item => item.path === "/game/saves")).toBe(false);
});

test("SPEC-190 verification link opens even with an existing authenticated session", async ({ page, backend }) => {
  backend.authenticated = true;
  let verified: unknown;
  await page.route("**/auth/config", route => route.fulfill(json({ ...unauthenticated,
    authenticated: true, user_id: "old-owner" })));
  await page.route("**/auth/verify", route => {
    verified = route.request().postDataJSON();
    return route.fulfill(json({ authenticated: true, csrf_token: "verified" }));
  });
  await page.goto("/#auth_action=verify&token_hash=private-verify-token");
  await expect(page).toHaveURL("http://127.0.0.1:4173/");
  await expect(page.getByRole("heading", { name: "Confirmar e-mail" })).toBeVisible();
  expect(backend.requests.some(item => item.path === "/game/saves")).toBe(false);
  await page.getByRole("button", { name: "Confirmar e-mail" }).click();
  await expect(page.getByRole("heading", { name: "Continuar jornada" })).toBeVisible();
  expect(verified).toEqual({ token_hash: "private-verify-token", type: "signup" });
});

test("SPEC-190 Turnstile binds each abuse flow to its server action", async ({ page, backend }) => {
  backend.authenticated = false;
  const actions: string[] = [];
  const captured: Record<string, unknown> = {};
  await page.addInitScript(() => {
    (window as typeof window & { turnstile: unknown }).turnstile = {
      render: (_: HTMLElement, options: { action: string; callback: (token: string) => void }) => {
        (window as typeof window & { __captchaActions: string[] }).__captchaActions.push(options.action);
        options.callback(`token-${options.action}`);
        return options.action;
      },
      remove: () => undefined,
    };
    (window as typeof window & { __captchaActions: string[] }).__captchaActions = [];
  });
  await page.route("**/auth/config", route => route.fulfill(json({ ...unauthenticated,
    captcha: { required: true, site_key: "test-site", provider: "turnstile" } })));
  await page.route("**/auth/signup", route => { captured.signup = route.request().postDataJSON();
    return route.fulfill(json({ authenticated: false }, 202)); });
  await page.route("**/auth/reset/request", route => { captured.reset = route.request().postDataJSON();
    return route.fulfill(json({ message: "ok" }, 202)); });
  await page.route("**/auth/verify/request", route => { captured.verify = route.request().postDataJSON();
    return route.fulfill(json({ message: "ok" }, 202)); });
  await page.goto("/");
  await page.getByRole("button", { name: "Criar uma conta local" }).click();
  await page.getByLabel("E-mail").fill("novo@example.test");
  await page.getByLabel("Senha", { exact: true }).fill("SenhaSegura123!");
  await page.getByLabel("Declaro ter 18 anos ou mais.").check(); // SPEC-222 R9
  await page.getByRole("button", { name: "Criar conta", exact: true }).click();
  await page.getByRole("button", { name: "Já tenho uma conta" }).click();
  await page.getByRole("button", { name: "Esqueci minha senha" }).click();
  await page.getByLabel("E-mail").fill("novo@example.test");
  await page.getByRole("button", { name: "Enviar recuperação" }).click();
  await page.getByRole("button", { name: "Voltar para entrar" }).click();
  await page.getByRole("button", { name: "Reenviar confirmação de e-mail" }).click();
  await page.getByLabel("E-mail").fill("novo@example.test");
  await page.getByRole("button", { name: "Enviar confirmação" }).click();
  actions.push(...await page.evaluate(() => (window as typeof window & { __captchaActions: string[] }).__captchaActions));
  expect(actions).toEqual(expect.arrayContaining(["signup", "reset", "verify"]));
  expect(captured).toMatchObject({ signup: { captcha_token: "token-signup" },
    reset: { captcha_token: "token-reset" }, verify: { captcha_token: "token-verify" } });
});

test("SPEC-190 required CAPTCHA without a site key fails closed in the browser", async ({ page, backend }) => {
  backend.authenticated = false;
  await page.route("**/auth/config", route => route.fulfill(json({ ...unauthenticated,
    captcha: { required: true, site_key: null, provider: "turnstile" } })));
  await page.goto("/");
  await page.getByRole("button", { name: "Criar uma conta local" }).click();
  await page.getByLabel("E-mail").fill("novo@example.test");
  await page.getByLabel("Senha", { exact: true }).fill("SenhaSegura123!");
  await expect(page.getByRole("alert")).toContainText("Verificação de segurança indisponível");
  await page.getByLabel("Declaro ter 18 anos ou mais.").check(); // SPEC-222 R9
  await expect(page.getByRole("button", { name: "Criar conta", exact: true })).toBeDisabled();
  expect(backend.requests.some(item => item.path === "/auth/signup")).toBe(false);
});

test("SPEC-190 export requires reauth and deletion can finish after session revocation", async ({ page, backend }) => {
  // The account cancels its own financial reads as soon as deletion starts.
  backend.allowFailure(/\/account\/(?:balance|series|usage|purchases|checkout(?:\/|$))/);
  backend.allowConsole(/server responded with a status of 403/); // Expected expired recent proof.
  let reauthCount = 0;
  let deleteCount = 0;
  let orderPolls = 0;
  let resolveDelete!: () => void;
  const deleteGate = new Promise<void>(resolve => { resolveDelete = resolve; });
  let notifyDeleteStarted!: () => void;
  const deleteStarted = new Promise<void>(resolve => { notifyDeleteStarted = resolve; });
  const orderId = "123e4567-e89b-42d3-a456-426614174100";
  await page.addInitScript(() => localStorage.setItem("cronicas_game_id", "game-a"));
  await page.route("**/auth/config", route => route.fulfill(json({ ...unauthenticated,
    authenticated: true, user_id: "owner-a" })));
  await page.route("**/auth/reauth", route => {
    expect(route.request().postDataJSON()).toEqual({ password: "MinhaSenha123!" });
    reauthCount++;
    return route.fulfill(json({ recent: true }));
  });
  await page.route("**/account/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === `/account/checkout/${orderId}`) {
      orderPolls++;
      return route.fulfill(json({ order_id: orderId, status: "checkout_pending" }));
    }
    if (path === "/account/export") return route.fulfill({ status: 200,
      headers: { "Content-Disposition": "attachment; filename=account.json" },
      contentType: "application/json", body: JSON.stringify({ owner_id: "owner-a", saves: [] }) });
    if (path === "/account/delete") {
      expect(route.request().postDataJSON()).toEqual({ confirmation: "EXCLUIR" });
      deleteCount++;
      if (deleteCount === 1) { notifyDeleteStarted(); await deleteGate; }
      if (deleteCount === 2) return route.fulfill(json({ detail: "recent_session_required" }, 403));
      return route.fulfill(json({ status: deleteCount === 1 ? "deleting" : "deleted" }, deleteCount === 1 ? 202 : 200));
    }
    if (path === "/account/balance") return route.fulfill(json({ available_milli: "0", reserved_milli: "0" }));
    if (path === "/account/series") return route.fulfill(json({ points: [], totals: { game: "0", image: "0", voice: "0" } }));
    return route.fulfill(json({ items: [], next_cursor: null }));
  });
  await page.goto(`/?checkout=success&order_id=${orderId}`);
  await expect.poll(() => orderPolls).toBeGreaterThan(0);
  const initialPolls = orderPolls;
  await expect(page.getByRole("heading", { name: "Dados e segurança da conta" })).toBeVisible();
  const severeAccessibilityIssues = (await new AxeBuilder({ page }).include(".account-lifecycle").analyze())
    .violations.filter(issue => ["serious", "critical"].includes(issue.impact ?? ""));
  expect(severeAccessibilityIssues).toEqual([]);
  await expect(page.getByRole("button", { name: "Baixar meus dados" })).toBeDisabled();
  await page.getByLabel("Senha atual").fill("MinhaSenha123!");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Baixar meus dados" }).click();
  expect((await download).suggestedFilename()).toBe("cronicas-valoria-conta.json");
  expect(reauthCount).toBe(1);
  await page.getByText("Excluir minha conta").click();
  await page.getByLabel("Senha atual").fill("MinhaSenha123!");
  await page.getByLabel("Digite EXCLUIR para confirmar").fill("EXCLUIR");
  const firstDeleteClick = page.getByRole("button", { name: "Excluir conta" }).click();
  await deleteStarted;
  await expect(page.getByRole("heading", { name: "Exclusão em andamento" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Minha conta" })).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.getItem("cronicas_game_id"))).toBeNull();
  await page.evaluate(() => window.dispatchEvent(new Event("rpg:auth-expired")));
  await expect(page.getByRole("heading", { name: "Exclusão em andamento" })).toBeVisible();
  resolveDelete();
  await firstDeleteClick;
  await page.waitForTimeout(5_300);
  expect(orderPolls).toBe(initialPolls);
  expect(reauthCount).toBe(2);
  await page.getByRole("button", { name: "Concluir exclusão" }).click();
  await expect(page.getByRole("alert")).toContainText("Confirme sua senha");
  await page.getByLabel("Senha atual").fill("MinhaSenha123!");
  await page.getByRole("button", { name: "Concluir exclusão" }).click();
  await expect(page.getByRole("heading", { name: "Retorne à fogueira" })).toBeVisible();
  expect(reauthCount).toBe(3);
  expect(deleteCount).toBe(3);
  expect(await page.evaluate(() => localStorage.getItem("cronicas_game_id"))).toBeNull();
});

test("SPEC-190 stale reauth from A cannot export or delete after B logs in", async ({ page, backend }) => {
  backend.userId = "owner-a";
  backend.allowFailure(/\/account\/(?:balance|series|usage|purchases|checkout(?:\/|$))/);
  let resumeReauth!: () => void;
  const reauthGate = new Promise<void>(resolve => { resumeReauth = resolve; });
  let reauthStarted!: () => void;
  const started = new Promise<void>(resolve => { reauthStarted = resolve; });
  let sensitiveCalls = 0;
  await page.route("**/auth/config", route => route.fulfill(json({ ...unauthenticated,
    authenticated: backend.authenticated, user_id: backend.userId })));
  await page.route("**/auth/reauth", async route => {
    reauthStarted();
    await reauthGate;
    return route.fulfill(json({ recent: true }));
  });
  await page.route("**/account/**", route => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/account/export" || path === "/account/delete") sensitiveCalls++;
    if (path === "/account/balance") return route.fulfill(json({ available_milli: "0", reserved_milli: "0" }));
    if (path === "/account/series") return route.fulfill(json({ points: [], totals: { game: "0", image: "0", voice: "0" } }));
    return route.fulfill(json({ items: [], next_cursor: null }));
  });
  await page.goto("/");
  await page.getByRole("button", { name: /Conta.*Estilhas/ }).click();
  await page.getByLabel("Senha atual").fill("MinhaSenha123!");
  await page.getByRole("button", { name: "Baixar meus dados" }).click();
  await started;
  await page.evaluate(() => window.dispatchEvent(new Event("rpg:auth-expired")));
  await expect(page.getByRole("heading", { name: "Retorne à fogueira" })).toBeVisible();
  backend.userId = "owner-b";
  await page.getByLabel("E-mail").fill("b@example.test");
  await page.getByLabel("Senha", { exact: true }).fill("MinhaSenha123!");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Continuar jornada" })).toBeVisible();
  resumeReauth();
  await page.waitForTimeout(200);
  expect(sensitiveCalls).toBe(0);
});

test("SPEC-190 native GoTrue CAPTCHA sends fresh tokens for login and each reauth", async ({ page, backend }) => {
  backend.authenticated = false;
  backend.userId = "owner-a";
  const loginBodies: unknown[] = [];
  const reauthBodies: unknown[] = [];
  await page.addInitScript(() => {
    let count = 0;
    (window as typeof window & { turnstile: unknown }).turnstile = {
      render: (_: HTMLElement, options: { action: string; callback: (token: string) => void }) => {
        count++;
        const token = `${options.action}-${count}`;
        options.callback(token);
        return token;
      },
      remove: () => undefined,
    };
  });
  await page.route("**/auth/config", route => route.fulfill(json({ ...unauthenticated,
    authenticated: backend.authenticated, user_id: backend.authenticated ? "owner-a" : undefined,
    captcha: { required: true, site_key: "test-site", provider: "turnstile", mode: "gotrue" } })));
  await page.route("**/auth/login", route => {
    loginBodies.push(route.request().postDataJSON());
    backend.authenticated = true;
    return route.fulfill(json({ authenticated: true, csrf_token: "csrf-login" }));
  });
  await page.route("**/auth/reauth", route => {
    reauthBodies.push(route.request().postDataJSON());
    return route.fulfill(json({ recent: true }));
  });
  await page.route("**/account/**", route => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/account/balance") return route.fulfill(json({ available_milli: "0", reserved_milli: "0" }));
    if (path === "/account/series") return route.fulfill(json({ points: [], totals: { game: "0", image: "0", voice: "0" } }));
    if (path === "/account/checkout/skus") return route.fulfill(json({ items: [] }));
    return route.fulfill(json({ items: [], next_cursor: null }));
  });
  await page.route("**/account/export", route => route.fulfill({ status: 200,
    contentType: "application/json", body: JSON.stringify({ owner_id: "owner-a", saves: [] }) }));
  await page.goto("/");
  await page.getByLabel("E-mail").fill("a@example.test");
  await page.getByLabel("Senha", { exact: true }).fill("MinhaSenha123!");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByRole("heading", { name: "Continuar jornada" })).toBeVisible();
  await page.getByRole("button", { name: /Conta.*Estilhas/ }).click();
  await page.getByLabel("Senha atual").fill("MinhaSenha123!");
  const firstDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Baixar meus dados" }).click();
  await firstDownload;
  await page.getByLabel("Senha atual").fill("MinhaSenha123!");
  const secondDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Baixar meus dados" }).click();
  await secondDownload;
  expect(loginBodies).toMatchObject([{ captcha_token: expect.stringMatching(/^login-\d+$/) }]);
  expect(reauthBodies).toMatchObject([
    { captcha_token: expect.stringMatching(/^reauth-\d+$/) },
    { captcha_token: expect.stringMatching(/^reauth-\d+$/) },
  ]);
  expect(reauthBodies).toHaveLength(2);
  expect((reauthBodies[0] as { captcha_token: string }).captcha_token)
    .not.toBe((reauthBodies[1] as { captcha_token: string }).captcha_token);
});
