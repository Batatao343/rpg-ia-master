// SSE controlado (SPEC-316 §3.1), compartilhado por turn-wait e action-queue (SPEC-427): puro movimento.
import { expect } from "@playwright/test";
import type { Page } from "@playwright/test";

export type SseWindow = Window & { __sseReqs: Array<Record<string, unknown>>; __sse: { push(t: string): void; close(): void } };

/** Chamar ANTES do `goto`: troca o fetch de `/game/action/stream` por um stream que o teste empurra. */
export async function installControlledSse(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as SseWindow;
    w.__sseReqs = [];
    const orig = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof Request ? input.url : String(input);
      if (!url.includes("/game/action/stream")) return orig(input, init);
      w.__sseReqs.push(JSON.parse(String(init?.body ?? "{}")));
      const enc = new TextEncoder();
      let ctrl!: ReadableStreamDefaultController<Uint8Array>;
      const body = new ReadableStream<Uint8Array>({ start(c) { ctrl = c; } });
      w.__sse = { push: (t: string) => ctrl.enqueue(enc.encode(t)), close: () => ctrl.close() };
      return Promise.resolve(new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } }));
    };
  });
}
export const ev = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
export const push = (page: Page, text: string) => page.evaluate((t) => (window as unknown as SseWindow).__sse.push(t), text);
export const closeSse = (page: Page) => page.evaluate(() => (window as unknown as SseWindow).__sse.close());
export const sseReqs = (page: Page) => page.evaluate(() => (window as unknown as SseWindow).__sseReqs);
export async function waitSseReqs(page: Page, n: number) {
  await expect.poll(async () => (await sseReqs(page)).length).toBe(n);
}
/** `state` final: o estado atual do jogo com a narração final (como o api.py). */
export async function finalState(page: Page, message: string) {
  const state = await page.evaluate(async () => (await fetch("/game/state?game_id=game-a")).json());
  return { ...state, message, message_type: "STORY" };
}

