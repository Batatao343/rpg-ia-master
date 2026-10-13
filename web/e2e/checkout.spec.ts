import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "./fixtures";

const orderId = "123e4567-e89b-42d3-a456-426614174100";
const sku = { sku_id: "starter-web-v1", gross_brl: "9.90", shard_milli: "5000" };

async function openAccount(page: import("@playwright/test").Page) {
  await page.route("https://fonts.googleapis.com/**", route =>
    route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.goto("/");
  await page.getByRole("button", { name: /Conta.*Estilhas/ }).click();
  await expect(page.getByRole("heading", { name: "Minha conta" })).toBeVisible();
}

for (const width of [390, 1440]) {
  test(`SPEC-189 only a published server SKU can start Checkout at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 850 });
    const checkouts: Record<string, unknown>[] = [];
    await page.route("https://checkout.stripe.com/**", route => route.fulfill({
      status: 200, contentType: "text/html", body: "<title>Stripe Checkout test</title>",
    }));
    await page.route("**/account/**", route => {
      const { pathname } = new URL(route.request().url());
      if (pathname === "/account/checkout/skus") return route.fulfill({ status: 200,
        contentType: "application/json", body: JSON.stringify({ items: [sku] }) });
      if (pathname === "/account/checkout" && route.request().method() === "POST") {
        checkouts.push(route.request().postDataJSON());
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
          order_id: orderId, status: "checkout_pending", checkout_url: "https://checkout.stripe.com/c/pay/test",
          ...sku,
        }) });
      }
      const body = pathname.endsWith("/balance") ? { available_milli: "0", reserved_milli: "0" }
        : pathname.endsWith("/series") ? { period: "7d", unit: "milli_shard",
          totals: { game: "0", image: "0", voice: "0" }, points: [] }
          : { items: [], next_cursor: null };
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    });
    await openAccount(page);
    await expect(page.getByText(/5 Estilhas.*R\$\s*9,90/)).toBeVisible();
    expect(checkouts).toHaveLength(0);
    const issues = (await new AxeBuilder({ page }).include(".account-screen").analyze())
      .violations.filter(v => ["serious", "critical"].includes(v.impact ?? ""));
    expect(issues).toEqual([]);
    await page.getByRole("button", { name: "Comprar pacote" }).click();
    await expect(page).toHaveURL("https://checkout.stripe.com/c/pay/test");
    expect(checkouts).toHaveLength(1);
    expect(checkouts[0]).toEqual({ sku_id: sku.sku_id, request_id: expect.stringMatching(/^[0-9a-f-]{36}$/) });
  });
}

test("SPEC-189 disabled catalog never exposes a purchase action", async ({ page, backend }) => {
  backend.allowFailure(/\/account\/checkout\/skus$/);
  backend.allowConsole(/503/);
  await page.route("**/account/**", route => {
    const { pathname } = new URL(route.request().url());
    if (pathname === "/account/checkout/skus") return route.fulfill({ status: 503,
      contentType: "application/json", body: JSON.stringify({ detail: "checkout_disabled" }) });
    const body = pathname.endsWith("/balance") ? { available_milli: "0", reserved_milli: "0" }
      : pathname.endsWith("/series") ? { period: "7d", unit: "milli_shard",
        totals: { game: "0", image: "0", voice: "0" }, points: [] }
        : { items: [], next_cursor: null };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await openAccount(page);
  await expect(page.getByText("A compra de Estilhas ainda não está disponível.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Comprar pacote" })).toHaveCount(0);
});

test("SPEC-189 retry reuses the request ID and accepts a terminal server replay", async ({ page, backend }) => {
  backend.allowFailure(/\/account\/checkout$/);
  backend.allowConsole(/503/);
  const requestIds: string[] = [];
  await page.route("**/account/**", route => {
    const { pathname } = new URL(route.request().url());
    if (pathname === "/account/checkout/skus") return route.fulfill({ status: 200,
      contentType: "application/json", body: JSON.stringify({ items: [sku] }) });
    if (pathname === "/account/checkout" && route.request().method() === "POST") {
      requestIds.push(route.request().postDataJSON().request_id);
      return route.fulfill({ status: requestIds.length === 1 ? 503 : 200,
        contentType: "application/json", body: JSON.stringify(requestIds.length === 1
          ? { detail: "temporarily_unavailable" }
          : { order_id: orderId, status: "paid", checkout_url: null, ...sku }) });
    }
    const body = pathname.endsWith("/balance") ? { available_milli: "0", reserved_milli: "0" }
      : pathname.endsWith("/series") ? { period: "7d", unit: "milli_shard",
        totals: { game: "0", image: "0", voice: "0" }, points: [] }
        : { items: [], next_cursor: null };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await openAccount(page);
  await page.getByRole("button", { name: "Comprar pacote" }).click();
  await expect(page.getByRole("alert")).toContainText("Você pode tentar novamente");
  await page.getByRole("button", { name: "Comprar pacote" }).click();
  await expect(page.getByRole("status")).toContainText("já foi confirmado pelo servidor");
  expect(requestIds).toHaveLength(2);
  expect(requestIds[0]).toBe(requestIds[1]);
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("region", { name: "Saldo de Estilhas" })).toContainText("0 Estilhas");
  await page.getByRole("button", { name: "Comprar pacote" }).click();
  await expect.poll(() => requestIds.length).toBe(3);
  expect(requestIds[2]).not.toBe(requestIds[1]);
});

test("SPEC-189 success redirect waits for a paid order and never grants locally", async ({ page, backend }) => {
  backend.allowFailure(new RegExp(`/account/checkout/${orderId}$`)); // StrictMode aborts its first poll.
  let orderStatus: "checkout_pending" | "paid" = "checkout_pending";
  let balance = "0";
  const requested: string[] = [];
  await page.route("**/account/**", route => {
    const { pathname } = new URL(route.request().url());
    requested.push(pathname);
    const body = pathname.endsWith(`/checkout/${orderId}`) ? { order_id: orderId, status: orderStatus, ...sku }
      : pathname.endsWith("/checkout/skus") ? { items: [] }
        : pathname.endsWith("/balance") ? { available_milli: balance, reserved_milli: "0" }
          : pathname.endsWith("/series") ? { period: "7d", unit: "milli_shard",
            totals: { game: "0", image: "0", voice: "0" }, points: [] }
            : { items: orderStatus === "paid" ? [{ id: "purchase-1", kind: "purchase",
              created_at: new Date().toISOString(), amount_milli: "5000" }] : [], next_cursor: null };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto(`/?checkout=success&order_id=${orderId}`);
  await expect(page.getByRole("heading", { name: "Minha conta" })).toBeVisible();
  await expect(page.getByText("Aguardando confirmação do pagamento. Nenhum crédito será antecipado.")).toBeVisible();
  await expect(page.getByRole("region", { name: "Saldo de Estilhas" })).toContainText("0 Estilhas");
  expect(requested).not.toContain("/account/checkout");
  orderStatus = "paid";
  balance = "5000"; // The fixture's server wallet, never the redirect, changes the balance.
  await page.getByRole("button", { name: "Atualizar status do pedido" }).click();
  await expect(page.getByText("Pagamento confirmado pelo servidor.", { exact: false })).toBeVisible();
  await expect(page.getByRole("region", { name: "Saldo de Estilhas" })).toContainText("5 Estilhas");
  await page.getByRole("button", { name: /Voltar/ }).click();
  await expect(page.getByRole("button", { name: "Conta · 5 Estilhas" })).toBeVisible();
});

test("SPEC-189 delayed account snapshot cannot overwrite a later paid balance", async ({ page, backend }) => {
  backend.allowFailure(new RegExp(`/account/checkout/${orderId}$`));
  let releaseStale!: () => void;
  const staleGate = new Promise<void>(resolve => { releaseStale = resolve; });
  let paidKnown = false;
  let staleReads = 0;
  await page.route("**/account/**", async route => {
    const { pathname } = new URL(route.request().url());
    if (pathname.endsWith(`/checkout/${orderId}`)) paidKnown = true;
    if (pathname.endsWith("/balance") && !paidKnown) {
      staleReads++;
      await staleGate;
      return route.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ available_milli: "0", reserved_milli: "0" }) });
    }
    const body = pathname.endsWith(`/checkout/${orderId}`) ? { order_id: orderId, status: "paid", ...sku }
      : pathname.endsWith("/checkout/skus") ? { items: [] }
        : pathname.endsWith("/balance") ? { available_milli: "5000", reserved_milli: "0" }
          : pathname.endsWith("/series") ? { period: "7d", unit: "milli_shard",
            totals: { game: "0", image: "0", voice: "0" }, points: [] }
            : { items: [], next_cursor: null };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  const paidBalance = page.waitForResponse(async response => response.url().endsWith("/account/balance")
    && response.ok() && (await response.json()).available_milli === "5000");
  await page.goto(`/?checkout=success&order_id=${orderId}`);
  await paidBalance;
  releaseStale();
  expect(staleReads).toBeGreaterThan(1); // App bootstrap and AccountScreen's initial snapshot.
  await expect(page.getByRole("region", { name: "Saldo de Estilhas" })).toContainText("5 Estilhas");
  await expect(page.getByText("Pagamento confirmado pelo servidor.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: /Voltar/ }).click();
  await expect(page.getByRole("button", { name: "Conta · 5 Estilhas" })).toBeVisible();
});

test("SPEC-189 cancel redirect still consults server order status", async ({ page, backend }) => {
  backend.allowFailure(new RegExp(`/account/checkout/${orderId}$`)); // StrictMode aborts its first poll.
  let orderGets = 0;
  await page.route("**/account/**", route => {
    const { pathname } = new URL(route.request().url());
    if (pathname.endsWith(`/checkout/${orderId}`)) orderGets++;
    const body = pathname.endsWith(`/checkout/${orderId}`) ? { order_id: orderId, status: "paid", ...sku }
      : pathname.endsWith("/checkout/skus") ? { items: [] }
        : pathname.endsWith("/balance") ? { available_milli: "5000", reserved_milli: "0" }
          : pathname.endsWith("/series") ? { period: "7d", unit: "milli_shard",
            totals: { game: "0", image: "0", voice: "0" }, points: [] }
            : { items: [], next_cursor: null };
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto(`/?checkout=cancel&order_id=${orderId}`);
  await expect(page.getByText("Você saiu do Checkout.", { exact: false })).toBeVisible();
  await expect(page.getByText("Pagamento confirmado pelo servidor.", { exact: false })).toBeVisible();
  expect(orderGets).toBeGreaterThan(0);
});
