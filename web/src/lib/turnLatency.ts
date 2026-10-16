// SPEC-200: marcas de latencia percebida por turno (ack, TTFMC, TTLT) via `performance`.
// Puro e injetavel (sem React): o rastreador recebe `now/mark/measure` para teste.
// Definicoes (normativas): ver docs/spec200/README.md.
//   ack   = do submit ate o PRIMEIRO BYTE do corpo SSE (o evento `accepted` e o ping nao sao conteudo)
//   ttfmc = do submit ate o primeiro `narrative` com `chunk.trim()` nao vazio
//   ttlt  = do submit ate o `narrative` com `done: true`
//   state = do submit ate o evento `state`
// Nenhum texto do jogador/narracao passa por aqui; so ids e milissegundos.

export type TurnMark = "submit" | "ack" | "first_phase" | "ttfmc" | "ttlt" | "state";
export type TurnTransport = "stream" | "post";
export type TurnOutcome = "ok" | "error" | "aborted";

export interface PerfLike {
  now(): number;
  mark(name: string): unknown;
  measure(name: string, start: string, end: string): unknown;
  /** Opcional: remove entradas antigas (sessões longas não acumulam marcas). */
  clear?(name: string): void;
}

/** Quantos turnos recentes mantêm marcas/medidas no buffer do navegador. */
export const KEEP_RECENT_TURNS = 3;
const recentNames: string[][] = [];

export interface LatencySummary {
  action_id: string;
  transport: TurnTransport;
  ack_ms: number | null;
  first_phase_ms: number | null;
  ttfmc_ms: number | null;
  ttlt_ms: number | null;
  state_ms: number | null;
  outcome: TurnOutcome;
}

const PREFIX = "rpg:turn:";

export function defaultPerf(): PerfLike | null {
  const p = (globalThis as { performance?: Partial<PerfLike> }).performance;
  if (!p || typeof p.now !== "function") return null;
  return {
    now: () => p.now!(),
    mark: (n) => { try { return typeof p.mark === "function" ? p.mark(n) : undefined; } catch { return undefined; } },
    measure: (n, s, e) => { try { return typeof p.measure === "function" ? p.measure(n, s, e) : undefined; } catch { return undefined; } },
    clear: (n) => {
      try {
        const q = p as { clearMarks?: (x: string) => void; clearMeasures?: (x: string) => void };
        q.clearMarks?.(n);
        q.clearMeasures?.(`${n}:ms`);
      } catch { /* buffer de performance é best-effort */ }
    },
  };
}

export class TurnLatencyTracker {
  private readonly times = new Map<TurnMark, number>();
  private outcome: TurnOutcome = "ok";

  constructor(
    readonly actionId: string,
    readonly transport: TurnTransport = "stream",
    private readonly perf: PerfLike | null = defaultPerf(),
  ) {}

  private name(mark: TurnMark): string { return `${PREFIX}${this.actionId}:${mark}`; }

  /** Marca a primeira ocorrencia; `submit` precisa vir antes de qualquer outra. */
  mark(mark: TurnMark): void {
    if (this.times.has(mark) || !this.perf) return;
    if (mark !== "submit" && !this.times.has("submit")) return;
    this.times.set(mark, this.perf.now());
    if (mark === "submit") this.rotateOldTurns();
    this.perf.mark(this.name(mark));
    recentNames[recentNames.length - 1]?.push(this.name(mark));
    if (mark !== "submit") this.perf.measure(`${this.name(mark)}:ms`, this.name("submit"), this.name(mark));
  }

  submit(): void { this.mark("submit"); }

  /** Abre o grupo deste turno e limpa marcas de turnos além dos KEEP_RECENT_TURNS. */
  private rotateOldTurns(): void {
    recentNames.push([]);
    while (recentNames.length > KEEP_RECENT_TURNS) {
      for (const n of recentNames.shift() ?? []) this.perf?.clear?.(n);
    }
  }

  /** Primeiro byte do corpo SSE (qualquer coisa, inclusive `accepted`/ping). */
  firstBytes(): void { this.mark("ack"); }

  /** Evento SSE decodificado. `accepted` e ping nunca definem TTFMC. */
  event(name: string, payload?: unknown): void {
    if (name === "phase") this.mark("first_phase");
    else if (name === "narrative") {
      const data = (payload ?? {}) as { chunk?: unknown; done?: unknown };
      if (typeof data.chunk === "string" && data.chunk.trim() !== "") this.mark("ttfmc");
      if (data.done === true) this.mark("ttlt");
    } else if (name === "state") this.mark("state");
  }

  /** Fallback POST: nao ha streaming, ttfmc = ttlt = state = resposta completa. */
  completePost(): void {
    this.mark("ack");
    this.mark("ttfmc");
    this.mark("ttlt");
    this.mark("state");
  }

  fail(outcome: TurnOutcome = "error"): void { this.outcome = outcome; }

  private ms(mark: TurnMark): number | null {
    const start = this.times.get("submit");
    const at = this.times.get(mark);
    return start === undefined || at === undefined ? null : Math.max(0, Math.round(at - start));
  }

  summary(): LatencySummary {
    return {
      action_id: this.actionId, transport: this.transport,
      ack_ms: this.ms("ack"), first_phase_ms: this.ms("first_phase"),
      ttfmc_ms: this.ms("ttfmc"), ttlt_ms: this.ms("ttlt"), state_ms: this.ms("state"),
      outcome: this.outcome,
    };
  }
}

// --- reporter opcional (desligado por default no servidor) -------------------
// O servidor sinaliza `client_latency_report: true` em /auth/config (ja buscado no
// bootstrap — nenhuma requisicao extra). Ausente => o cliente nunca envia.
type Sender = (body: LatencySummary) => Promise<unknown>;
let serverEnabled = false;
let disabledForSession = false;

export function setClientLatencyReport(enabled: boolean): void { serverEnabled = enabled === true; }

export async function reportClientLatency(summary: LatencySummary, send: Sender): Promise<boolean> {
  if (!serverEnabled || disabledForSession) return false;
  try {
    await send(summary);
    return true;
  } catch {
    disabledForSession = true;          // desiste apos a primeira falha
    return false;
  }
}

export function resetReporterForTests(): void { serverEnabled = false; disabledForSession = false; }
