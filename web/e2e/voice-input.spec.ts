import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { test, expect } from "./fixtures";

test.use({ hasTouch: true });

async function fakeMicrophone(page: Page, permission: "granted" | "denied" | "pending" = "granted", mime = "audio/webm;codecs=opus") {
  await page.addInitScript(({ permission, mime }) => {
    const audit = { captures: 0, stops: 0, releases: 0, grant: () => {} };
    Object.assign(window, { voiceAudit: audit });
    const NativeXHR = XMLHttpRequest;
    class ObservedXHR extends NativeXHR {
      constructor() { super(); Object.assign(window, { voiceXHR: this }); }
    }
    Object.defineProperty(window, "XMLHttpRequest", { value: ObservedXHR });
    const stream = { getTracks: () => [{ stop() { audit.releases++; } }] };
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: {
      getUserMedia: async () => {
        audit.captures++;
        if (permission === "denied") throw new DOMException("denied", "NotAllowedError");
        if (permission === "pending") return new Promise(resolve => { audit.grant = () => resolve(stream); });
        return stream;
      },
    } });
    class FakeRecorder {
      static isTypeSupported(type: string) { return type === mime; }
      state = "inactive";
      mimeType = mime;
      ondataavailable?: (event: { data: Blob }) => void;
      onstop?: () => void;
      start() { this.state = "recording"; }
      stop() {
        audit.stops++; this.state = "inactive";
        queueMicrotask(() => {
          this.ondataavailable?.({ data: new Blob(["binary-voice-fixture"], { type: mime }) });
          this.onstop?.();
        });
      }
    }
    Object.defineProperty(window, "MediaRecorder", { configurable: true, value: FakeRecorder });
  }, { permission, mime });
}
async function open(page: Page) {
  await page.route("https://fonts.googleapis.com/**", route => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.goto("/");
  await page.getByRole("button", { name: /^Ayla/ }).click();
  await expect(page.getByLabel("Sua ação")).toBeVisible();
}
const audit = (page: Page) => page.evaluate(() => (window as unknown as { voiceAudit: { captures: number; stops: number; releases: number } }).voiceAudit);

for (const width of [390, 1440]) {
  test(`SPEC-187 editable transcript, explicit send and a11y at ${width}`, async ({ page, backend }) => {
    await page.setViewportSize({ width, height: 850 });
    await fakeMicrophone(page, "granted", width === 390 ? "audio/mp4" : "audio/webm;codecs=opus");
    let uploads = 0;
    let finish!: () => void;
    const gate = new Promise<void>(resolve => { finish = resolve; });
    await page.context().addCookies([{ name: "rpg_csrf", value: "voice-csrf", url: "http://127.0.0.1:4173" }]);
    await page.route("**/account/transcriptions", async route => {
      uploads++;
      expect(route.request().headers()["x-csrf-token"]).toBe("voice-csrf");
      expect(route.request().headers()["x-operation-id"]).toMatch(/^[0-9a-f-]{36}$/);
      expect(route.request().headers()["content-type"]).toBe(width === 390 ? "audio/mp4" : "audio/webm;codecs=opus");
      expect(route.request().postDataBuffer()?.toString()).toBe("binary-voice-fixture");
      // Route interception holds network progress until fulfillment. Deliver the
      // browser upload-complete event after the stub receives the binary body.
      await page.evaluate(() => (window as unknown as { voiceXHR: XMLHttpRequest }).voiceXHR.upload.dispatchEvent(new ProgressEvent("load")));
      await gate;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ text: "Examino a porta", billing_status: "settled" }) });
    });
    await open(page);
    await page.getByLabel("Sua ação").fill("Com cuidado,");
    const record = page.getByRole("button", { name: "Gravar ação por voz" });
    if (width === 1440) { await record.focus(); await record.press("Space"); }
    else await record.tap();
    await expect(page.locator('[data-voice-state="recording"]')).toBeVisible();
    await expect(page.getByLabel("Tempo de gravação")).toContainText("/ 60 s");
    await expect(page.getByLabel("Sua ação")).toBeEnabled();
    const issues = (await new AxeBuilder({ page }).analyze()).violations.filter(v => ["serious", "critical"].includes(v.impact ?? ""));
    expect(issues).toEqual([]);
    await page.getByRole("button", { name: "Parar gravação" }).press("Enter");
    await expect(page.locator('[data-voice-state="transcribing"]')).toBeVisible();
    await page.getByLabel("Sua ação").fill("Silenciosamente,");
    finish();
    await expect(page.getByLabel("Sua ação")).toHaveValue("Silenciosamente, Examino a porta");
    expect(uploads).toBe(1); expect((await audit(page)).releases).toBeGreaterThan(0);
    expect(backend.requests.filter(r => /\/game\/action/.test(r.path))).toHaveLength(0);
    await page.getByLabel("Sua ação").fill("Examino a porta azul");
    await page.getByLabel("Sua ação").press("Enter");
    await expect(page.getByText("O mundo responde a: Examino a porta azul")).toBeVisible();
    expect(backend.requests.filter(r => /\/game\/action/.test(r.path))).toHaveLength(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const boxes = await Promise.all([page.getByLabel("Sua ação"), record, page.getByRole("button", { name: "Agir" })].map(e => e.boundingBox()));
    expect(boxes[0]!.x + boxes[0]!.width).toBeLessThanOrEqual(boxes[1]!.x);
    expect(boxes[1]!.x + boxes[1]!.width).toBeLessThanOrEqual(boxes[2]!.x);
  });

  test(`SPEC-187 permission denied and failed STT preserve typed actions at ${width}`, async ({ page, backend }) => {
    await page.setViewportSize({ width, height: 850 }); await fakeMicrophone(page, "denied"); await open(page);
    await page.getByLabel("Sua ação").fill("Meu texto permanece");
    await page.getByRole("button", { name: "Gravar ação por voz" }).click();
    await expect(page.getByRole("alert")).toContainText("Permissão do microfone negada");
    await expect(page.getByLabel("Sua ação")).toHaveValue("Meu texto permanece");
    await expect(page.getByLabel("Sua ação")).toBeEnabled();
    await page.getByRole("button", { name: "Agir" }).click();
    await expect(page.getByText("O mundo responde a: Meu texto permanece")).toBeVisible();
    expect(backend.requests.filter(r => /\/game\/action/.test(r.path))).toHaveLength(1);
  });
}

test("SPEC-187 STT failure preserves edits and permits ordinary text send", async ({ page, backend }) => {
  await fakeMicrophone(page); backend.allowConsole(/422/);
  await page.route("**/account/transcriptions", route => route.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify({ detail: "Áudio inválido" }) }));
  await open(page); await page.getByLabel("Sua ação").fill("Não perder este texto");
  await page.getByRole("button", { name: "Gravar ação por voz" }).click();
  await page.getByRole("button", { name: "Parar gravação" }).click();
  await expect(page.getByRole("alert")).toContainText("Áudio inválido");
  await expect(page.getByLabel("Sua ação")).toHaveValue("Não perder este texto");
  expect(backend.requests.filter(r => /\/game\/action/.test(r.path))).toHaveLength(0);
  await page.getByLabel("Sua ação").press("Enter");
  await expect(page.getByText("O mundo responde a: Não perder este texto")).toBeVisible();
});

test("SPEC-187 hard stop after 60s uploads once without sending action", async ({ page, backend }) => {
  await fakeMicrophone(page); let uploads = 0;
  await page.route("**/account/transcriptions", route => { uploads++; return route.fulfill({ status: 200, contentType: "application/json", body: '{"text":"Aguardo"}' }); });
  await open(page); await page.clock.install();
  await page.getByRole("button", { name: "Gravar ação por voz" }).click();
  await expect(page.getByRole("button", { name: "Parar gravação" })).toBeVisible();
  await page.clock.fastForward(59_000); expect((await audit(page)).stops).toBe(0);
  await page.clock.fastForward(1_000);
  await expect(page.getByLabel("Sua ação")).toHaveValue("Aguardo");
  expect(uploads).toBe(1); expect((await audit(page)).stops).toBe(1);
  expect(backend.requests.filter(r => /\/game\/action/.test(r.path))).toHaveLength(0);
});

test("SPEC-187 background, pagehide, cancellation and unmount release tracks without uploads", async ({ page, backend }) => {
  await fakeMicrophone(page); let uploads = 0;
  await page.route("**/account/transcriptions", route => { uploads++; return route.fulfill({ status: 200, body: '{"text":"unexpected"}' }); });
  await open(page);
  for (const event of ["visibilitychange", "pagehide", "cancel", "unmount"]) {
    await page.getByRole("button", { name: "Gravar ação por voz" }).click();
    await expect(page.getByRole("button", { name: "Parar gravação" })).toBeVisible();
    if (event === "cancel") await page.getByRole("button", { name: "Cancelar voz" }).click();
    else if (event === "unmount") await page.getByRole("button", { name: "Nova", exact: true }).click();
    else await page.evaluate(event => {
      if (event === "visibilitychange") {
        Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
        document.dispatchEvent(new Event(event));
        Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
      } else window.dispatchEvent(new Event(event));
    }, event);
    await expect.poll(async () => (await audit(page)).stops).toBe(["visibilitychange", "pagehide", "cancel", "unmount"].indexOf(event) + 1);
  }
  expect((await audit(page)).releases).toBeGreaterThanOrEqual(4); expect(uploads).toBe(0);
  expect(backend.requests.filter(r => /\/game\/action/.test(r.path))).toHaveLength(0);
});

test("SPEC-187 cancelled permission request cleans a late grant", async ({ page }) => {
  await fakeMicrophone(page, "pending"); await open(page);
  await page.getByRole("button", { name: "Gravar ação por voz" }).click();
  await page.getByRole("button", { name: "Cancelar voz" }).click();
  await page.evaluate(() => (window as unknown as { voiceAudit: { grant(): void } }).voiceAudit.grant());
  await expect.poll(async () => (await audit(page)).releases).toBeGreaterThan(0);
  await expect(page.locator('[data-voice-state="idle"]')).toBeVisible();
});

test("SPEC-187 same component session change resets voice state and idle background is a no-op", async ({ page }) => {
  await fakeMicrophone(page);
  await page.goto("/tests/voice-hook.fixture.html");
  await page.getByRole("button", { name: "Record fixture" }).click();
  await expect(page.getByTestId("phase")).toHaveText("recording");
  await page.getByRole("button", { name: "Switch session" }).click();
  await expect(page.getByTestId("phase")).toHaveText("idle");
  expect((await audit(page)).releases).toBeGreaterThan(0);
  await page.evaluate(() => window.dispatchEvent(new Event("pagehide")));
  await expect(page.getByTestId("message")).toBeEmpty();
  await page.getByRole("button", { name: "Record fixture" }).click();
  await expect(page.getByTestId("phase")).toHaveText("recording");
  await page.getByRole("button", { name: "Toggle mount" }).click();
  expect((await audit(page)).stops).toBe(2);
  await page.getByRole("button", { name: "Toggle mount" }).click();
  await expect(page.getByTestId("phase")).toHaveText("idle");
});

test("SPEC-187 unmount aborts a pending upload and drops its late transcript", async ({ page, backend }) => {
  await fakeMicrophone(page);
  backend.allowFailure(/\/account\/transcriptions$/);
  let finish!: () => void; const gate = new Promise<void>(resolve => { finish = resolve; });
  let requested = false;
  await page.route("**/account/transcriptions", async route => {
    requested = true; await gate;
    try { await route.fulfill({ status: 200, contentType: "application/json", body: '{"text":"Late old-session transcript"}' }); }
    catch (error) { if (!/closed|intercepted|handled/i.test(String(error))) throw error; }
  });
  await page.goto("/tests/voice-hook.fixture.html");
  await page.getByRole("button", { name: "Record fixture" }).click();
  await expect(page.getByTestId("phase")).toHaveText("recording");
  await page.getByRole("button", { name: "Stop fixture" }).click();
  await expect.poll(() => requested).toBe(true);
  const failed = page.waitForEvent("requestfailed", { predicate: request => request.url().endsWith("/account/transcriptions") });
  await page.getByRole("button", { name: "Toggle mount" }).click();
  await failed; finish();
  await page.getByRole("button", { name: "Toggle mount" }).click();
  await expect(page.getByLabel("Transcript")).toHaveValue("");
  await expect(page.getByTestId("phase")).toHaveText("idle");
});

test("SPEC-187 native Chromium MediaRecorder produces a browser audio Blob and releases its track", async ({ page, backend }) => {
  await page.addInitScript(() => {
    const NativeRecorder = MediaRecorder;
    const state = { chunks: 0, track: null as MediaStreamTrack | null };
    Object.assign(window, { nativeVoice: state });
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: {
      getUserMedia: async () => {
        const context = new AudioContext(); await context.resume();
        const destination = context.createMediaStreamDestination();
        const tone = context.createOscillator(); tone.frequency.value = 220;
        tone.connect(destination); tone.start();
        const track = state.track = destination.stream.getAudioTracks()[0];
        const stop = track.stop.bind(track);
        track.stop = () => { if (track.readyState === "ended") return; stop(); tone.stop(); void context.close(); };
        return destination.stream;
      },
    } });
    class ObservedRecorder extends NativeRecorder {
      constructor(stream: MediaStream, options: MediaRecorderOptions) {
        super(stream, options);
        this.addEventListener("dataavailable", event => { if (event.data.size) state.chunks++; });
      }
    }
    Object.defineProperty(window, "MediaRecorder", { value: ObservedRecorder });
  });
  let bytes = 0;
  await page.route("**/account/transcriptions", route => {
    bytes = route.request().postDataBuffer()!.byteLength;
    expect(route.request().headers()["content-type"]).toMatch(/^audio\/(webm|ogg|mp4)/);
    return route.fulfill({ status: 200, contentType: "application/json", body: '{"text":"Transcript de fixture, sem chamada STT"}' });
  });
  await open(page); await page.getByRole("button", { name: "Gravar ação por voz" }).click();
  await expect.poll(() => page.evaluate(() => (window as unknown as { nativeVoice: { chunks: number } }).nativeVoice.chunks)).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Parar gravação" }).click();
  await expect(page.getByLabel("Sua ação")).toHaveValue("Transcript de fixture, sem chamada STT");
  expect(bytes).toBeGreaterThan(100);
  expect(await page.evaluate(() => (window as unknown as { nativeVoice: { track: MediaStreamTrack } }).nativeVoice.track.readyState)).toBe("ended");
  expect(backend.requests.filter(r => /\/game\/action/.test(r.path))).toHaveLength(0);
});
