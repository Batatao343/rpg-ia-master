// SPEC-212 (Etapa 0, autoria de eval): suporte da jornada vertical J-V1.
// A régua mora em evals/evaluators/gameplay_gate.py; aqui só coletamos o que a jornada
// observa (trace) e entregamos ao oráculo Python. Nada daqui altera estado de jogo fora das
// ações de jogador, nem chama provider real.
import AxeBuilder from "@axe-core/playwright";
import type { Page, Request, Response, TestInfo } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { inflateRawSync } from "node:zlib";
import { randomUUID } from "node:crypto";

export const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

/** R10: lista de tolerados, explícita e versionada (cada entrada justificada; nada genérico). */
export const VERTICAL_ALLOWLIST: readonly string[] = [
  // O beacon de latência (RPG_CLIENT_LATENCY_REPORT=1, ligado só pelo gate para medir R13) é um fetch
  // comum fire-and-forget (sem keepalive, KI-3); `page.reload()`/navegação da jornada o aborta e o Chromium
  // o reporta como `requestfailed ERR_ABORTED`.
  // A resposta chega (ledger.beaconFor lê o corpo); só esse caso exato é tolerado.
  "/telemetry/client-latency net::ERR_ABORTED$",
];

export function vjEnv() {
  return {
    base: process.env.RPG_VJ_BASE_URL ?? "",
    python: process.env.RPG_VJ_PYTHON ?? "",
    serviceKey: process.env.RPG_VJ_SERVICE_KEY ?? "",
    authUrl: process.env.RPG_VJ_AUTH_URL ?? "http://127.0.0.1:55321",
    apiLog: process.env.RPG_VJ_API_LOG ?? "",
    outDir: process.env.RPG_VJ_ARTIFACT_DIR ?? resolve(REPO_ROOT, "web/test-results/vertical"),
  };
}

/** Sem stack real provisionada a jornada não roda (o gate trata como `not_provisioned`). */
export function verticalProvisioned(): boolean {
  const e = vjEnv();
  return !!(e.base && e.python && e.serviceKey && e.apiLog);
}

export const viewportName = (info: TestInfo): string => {
  const vp = info.project.use.viewport;
  return vp ? `${vp.width}x${vp.height}` : "1440x900";
};

// --- conta sintética (só GoTrue local) ----------------------------------------------------

export async function createConfirmedUser(): Promise<{ id: string; email: string; password: string }> {
  const e = vjEnv();
  const host = new URL(e.authUrl).hostname;
  if (!["127.0.0.1", "localhost"].includes(host)) throw new Error("J-V1 só cria usuários no GoTrue local");
  const email = `vj-${randomUUID().slice(0, 8)}@example.test`;
  const password = `Vj-${randomUUID().slice(0, 12)}-2026!`;
  const res = await fetch(`${e.authUrl}/auth/v1/admin/users`, {
    method: "POST",
    headers: { apikey: e.serviceKey, Authorization: `Bearer ${e.serviceKey}`, "content-type": "application/json" },
    body: JSON.stringify({ email, password, email_confirm: true }),
  });
  if (!res.ok) throw new Error(`GoTrue admin recusou o usuário sintético: HTTP ${res.status}`);
  return { id: (await res.json()).id as string, email, password };
}

export async function deleteUser(id: string): Promise<void> {
  const e = vjEnv();
  await fetch(`${e.authUrl}/auth/v1/admin/users/${id}`, {
    method: "DELETE", headers: { apikey: e.serviceKey, Authorization: `Bearer ${e.serviceKey}` },
  }).catch(() => undefined);
}

// --- guardas globais (R10) ---------------------------------------------------------------------

export interface GuardEvent { kind: string; text?: string; url?: string; status?: number }

export class Guards {
  events: GuardEvent[] = [];
  /** Janela induzida pelo teste (reload no meio do SSE): aborts de rede dela são esperados. */
  induced = false;
  constructor(private origin: string) {}

  install(page: Page) {
    page.on("pageerror", (error) => this.events.push({ kind: "pageerror", text: error.message }));
    page.on("console", (m) => { if (m.type() === "error") this.events.push({ kind: "console_error", text: m.text() }); });
    page.on("response", (r: Response) => {
      if (r.status() >= 500) this.events.push({ kind: "http_5xx", url: r.url(), status: r.status() });
    });
    page.on("requestfailed", (r: Request) => {
      const err = r.failure()?.errorText ?? "";
      if (this.induced && /ERR_ABORTED|ERR_NETWORK_CHANGED|NS_BINDING_ABORTED/.test(err)) return;
      this.events.push({ kind: "request_failed", url: r.url(), text: err });
    });
    page.on("request", (r: Request) => {
      const url = r.url();
      if (!url.startsWith("data:") && !url.startsWith("blob:")) this.events.push({ kind: "request", url });
    });
  }

  section() {
    return { events: this.events, allowlist: [...VERTICAL_ALLOWLIST], expected_origins: [this.origin] };
  }
}

// --- ledger de turnos (R11/R13) ---------------------------------------------------------------

export interface TurnRecord {
  label: string;
  action_id: string;
  game_id: string;
  transport: "stream" | "post";
  http_status: number;
  accepted: boolean;
  replay: boolean;
  request_json: string;
  state: Record<string, any> | null;
  error_detail?: unknown;
}

export interface ClientBeacon {
  action_id: string; transport: string; ack_ms: number | null; first_phase_ms: number | null;
  ttfmc_ms: number | null; ttlt_ms: number | null; state_ms: number | null; outcome: string;
}

export function parseSseState(body: string): Record<string, any> | null {
  let state: Record<string, any> | null = null;
  for (const block of body.split(/\r?\n\r?\n/)) {
    const event = /^event: (.+)$/m.exec(block)?.[1];
    const data = /^data: (.+)$/m.exec(block)?.[1];
    if (event === "state" && data) state = JSON.parse(data);
  }
  return state;
}

export class TurnLedger {
  records: TurnRecord[] = [];
  beacons: ClientBeacon[] = [];
  private pending = new Map<string, Promise<void>>();

  install(page: Page) {
    page.on("response", (res: Response) => {
      const req = res.request();
      const path = new URL(req.url()).pathname;
      if (req.method() !== "POST") return;
      if (path === "/telemetry/client-latency") {
        try { this.beacons.push(req.postDataJSON() as ClientBeacon); } catch { /* corpo ilegível */ }
        return;
      }
      if (path !== "/game/action" && path !== "/game/action/stream") return;
      const body = (() => { try { return req.postDataJSON() as Record<string, any>; } catch { return {}; } })();
      const job = (async () => {
        let state: Record<string, any> | null = null;
        let detail: unknown;
        try {
          const text = await res.text();
          if (path.endsWith("/stream")) {
            state = parseSseState(text);
            if (!state) { const m = /^event: error\ndata: (.+)$/m.exec(text); if (m) detail = JSON.parse(m[1]); }
          } else {
            const json = JSON.parse(text);
            if (res.ok()) state = json; else detail = json;
          }
        } catch { /* corpo abortado (reload mid-SSE) */ }
        this.records.push({
          label: "", action_id: String(body.action_id ?? ""), game_id: String(body.game_id ?? ""),
          transport: path.endsWith("/stream") ? "stream" : "post", http_status: res.status(),
          accepted: !!state, replay: false, request_json: req.postData() ?? "", state, error_detail: detail,
        });
      })();
      this.pending.set(String(body.action_id ?? ""), job);
    });
  }

  async settled(actionId: string, timeout = 60_000): Promise<TurnRecord> {
    const start = Date.now();
    for (;;) {
      const job = this.pending.get(actionId);
      if (job) { await job; const rec = [...this.records].reverse().find((r) => r.action_id === actionId); if (rec) return rec; }
      if (Date.now() - start > timeout) throw new Error(`turno ${actionId} não terminou em ${timeout} ms`);
      await new Promise((r) => setTimeout(r, 100));
    }
  }

  async beaconFor(actionId: string, timeout = 15_000): Promise<ClientBeacon | null> {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const b = this.beacons.find((x) => x.action_id === actionId);
      if (b) return b;
      await new Promise((r) => setTimeout(r, 100));
    }
    return null;
  }
}

/** Linhas `evt: "turn"` (rpg.turn) do log da API; o gate entrega o arquivo em RPG_VJ_API_LOG. */
export function serverTurnLines(): Array<Record<string, any>> {
  const file = vjEnv().apiLog;
  if (!file || !existsSync(file)) return [];
  const out: Array<Record<string, any>> = [];
  for (const line of readFileSync(file, "utf-8").split(/\r?\n/)) {
    if (!line.startsWith("{") || !line.includes('"evt": "turn"')) continue;
    try { const j = JSON.parse(line); if (j.evt === "turn") out.push(j); } catch { /* linha parcial */ }
  }
  return out;
}

// --- a11y por aba (R15) -----------------------------------------------------------------------------

export async function axeRows(page: Page, viewport: string, tab: string) {
  const result = await new AxeBuilder({ page }).analyze();
  return {
    viewport, tab,
    violations: result.violations.map((v) => ({ id: v.id, impact: v.impact ?? "minor", help: v.help })),
  };
}

// --- ZIP de auditoria (SPEC-207) sem dependência: central directory + inflateRaw ---------

export function readZip(buf: Buffer): Record<string, string> {
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0; i--) if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  if (eocd < 0) throw new Error("ZIP sem EOCD");
  const count = buf.readUInt16LE(eocd + 10);
  let p = buf.readUInt32LE(eocd + 16);
  const files: Record<string, string> = {};
  for (let n = 0; n < count; n++) {
    if (buf.readUInt32LE(p) !== 0x02014b50) throw new Error("ZIP: diretório central corrompido");
    const method = buf.readUInt16LE(p + 10), csize = buf.readUInt32LE(p + 20);
    const nlen = buf.readUInt16LE(p + 28), xlen = buf.readUInt16LE(p + 30), clen = buf.readUInt16LE(p + 32);
    const local = buf.readUInt32LE(p + 42);
    const name = buf.toString("utf-8", p + 46, p + 46 + nlen);
    const dataStart = local + 30 + buf.readUInt16LE(local + 26) + buf.readUInt16LE(local + 28);
    const raw = buf.subarray(dataStart, dataStart + csize);
    files[name] = (method === 0 ? raw : inflateRawSync(raw)).toString("utf-8");
    p += 46 + nlen + xlen + clen;
  }
  return files;
}

/** PII que o export jamais pode conter (R9): e-mail da conta, ids e padrões genéricos. */
export function piiFindings(files: Record<string, string>, needles: string[]): string[] {
  const generic: Array<[string, RegExp]> = [
    ["email", /[\w.+-]+@[\w-]+\.[\w.-]+/],
    ["ipv4", /\b(?:\d{1,3}\.){3}\d{1,3}\b/],
    ["bearer", /Bearer\s+[\w.-]{16,}/],
    ["jwt", /eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}/],
    ["api_key", /\b(?:sk|pk|sb)_[A-Za-z0-9_-]{16,}/],
  ];
  const hits: string[] = [];
  for (const [name, text] of Object.entries(files)) {
    if (name === "AUDITOR_PROMPT.md" || name === "README_SCHEMA.md") continue; // docs estáticos
    for (const needle of needles) if (needle && text.includes(needle)) hits.push(`${name}: needle`);
    for (const [kind, rx] of generic) if (rx.test(text)) hits.push(`${name}: ${kind}`);
  }
  return hits;
}

// --- oráculo Python (régua em evals/) ---------------------------------------------------------------

export interface Verdict { ok: boolean; problems: Record<string, string[]>; baseline: Record<string, unknown> }

export function scanTrace(trace: Record<string, unknown>): Verdict {
  const e = vjEnv();
  try {
    const out = execFileSync(e.python, ["-m", "evals.gameplay_scan"], {
      cwd: REPO_ROOT, input: JSON.stringify(trace), encoding: "utf-8", maxBuffer: 32 * 1024 * 1024,
    });
    return JSON.parse(out) as Verdict;
  } catch (error) {
    const out = (error as { stdout?: string }).stdout;
    if (out) return JSON.parse(out) as Verdict; // exit 1 = problemas, vem no stdout
    throw error;
  }
}

export function writeTrace(viewport: string, trace: unknown): string {
  const dir = vjEnv().outDir;
  mkdirSync(dir, { recursive: true });
  const file = resolve(dir, `vertical-trace-${viewport}.json`);
  writeFileSync(file, JSON.stringify(trace, null, 2) + "\n", "utf-8");
  return file;
}
