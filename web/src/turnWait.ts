// SPEC-320: modelo puro da espera do turno (sem React) — testável em node:test.

/** Sem nenhum chunk de narração por tanto tempo: linha de tranquilização (D2). */
export const REASSURE_MS = 8000;
/** ... e por tanto tempo: "Continuar esperando" / "Tentar de novo" (D2). */
export const RETRY_MS = 25000;

/** idle = sem turno; waiting = aguardando narração; narrated = texto entregue, turno ainda não salvo
 *  (SPEC-316 `narrative done:true` → `state`); failed-after-narration = texto na tela, turno não salvo. */
export type TurnStage = "idle" | "waiting" | "narrated" | "failed-after-narration";

export type WaitTier = "none" | "reassure" | "retry";

export function waitTier(elapsedMs: number): WaitTier {
  if (elapsedMs >= RETRY_MS) return "retry";
  if (elapsedMs >= REASSURE_MS) return "reassure";
  return "none";
}

// spec streaming-turno-sse (R4): textos curados por nó/rota do grafo. Sem emoji (SPEC-320 R2).
export const PHASE_TEXTS: Record<string, string> = {
  campaign_manager: "O mestre consulta os arcanos…",
  dm_router: "O mestre decide o rumo…",
  storyteller: "O narrador tece o destino…",
  combat_agent: "O aço encontra o aço…",
  npc_actor: "Vozes se erguem…",
  loot_agent: "Algo reluz entre os despojos…",
  archivist: "O escriba registra a jornada…",
};
export const ROUTE_TEXTS: Record<string, string> = {
  combat_agent: "O aço encontra o aço…",
  npc_actor: "Vozes se erguem…",
  loot: "Algo reluz entre os despojos…",
  storyteller: "O narrador tece o destino…",
};

export interface PhaseLedger { phases: string[]; current: string | null }

export const EMPTY_LEDGER: PhaseLedger = { phases: [], current: null };

/** Livro-razão: a fase anterior passa a `phases` (sem duplicar); `label` vira a atual. */
export function addPhase(ledger: PhaseLedger, label: string | null): PhaseLedger {
  if (!label || label === ledger.current) return ledger;
  const phases = ledger.current && !ledger.phases.includes(ledger.current)
    ? [...ledger.phases, ledger.current] : ledger.phases;
  return { phases: phases.filter(p => p !== label), current: label };
}

/** Eventos que movem o `stage` (SPEC-316 §3.1). */
export type TurnEvent = "submit" | "narrative-done" | "state" | "error-after-narration" | "error" | "reset";

export function nextStage(stage: TurnStage, event: TurnEvent): TurnStage {
  switch (event) {
    case "submit": return "waiting";
    case "narrative-done": return stage === "waiting" ? "narrated" : stage;
    case "error-after-narration": return "failed-after-narration";
    case "state": case "error": case "reset": return "idle";
  }
}

/** Estado da espera do turno que o App entrega ao compositor (SPEC-320). */
export interface TurnWait {
  /** Muda a cada envio: reinicia estado local da linha de status (ex.: "Continuar esperando"). */
  seq: number;
  ledger: PhaseLedger;
  stage: TurnStage;
  /** Primeiro byte do SSE já lido (depois disso o botão mostra "Aguardando o narrador"). */
  acked: boolean;
  /** Já chegou algum chunk de narração (zera a contagem de tranquilização). */
  gotChunk: boolean;
  /** Último erro do turno; some no próximo envio. */
  error: { msg: string; kind: "error" | "warn" | "info"; requestId?: string } | null;
}

export const IDLE_TURN: TurnWait = { seq: 0, ledger: EMPTY_LEDGER, stage: "idle", acked: false, gotChunk: false, error: null };

/** Capitular (R11): só em abertura (1ª narração da sessão ou 1ª após trocar de local) e nunca sobre pontuação. */
export function openingAllowed(text: string, opening: boolean): boolean {
  return opening && !/^[—“"«]/.test(text.trimStart());
}

export interface OpeningMemo { gid: string; seen: boolean; loc: string }

/** Decide `opening` para a narração de `gid` em `loc`; devolve o novo memo (não muta). */
export function nextOpening(memo: OpeningMemo, gid: string, loc: string, text: string): { opening: boolean; memo: OpeningMemo } {
  const base = memo.gid === gid ? memo : { gid, seen: false, loc: "" };
  const changed = base.seen && !!loc && !!base.loc && loc !== base.loc;
  const opening = openingAllowed(text, !base.seen || changed);
  return { opening, memo: { gid, seen: true, loc: loc || base.loc } };
}
