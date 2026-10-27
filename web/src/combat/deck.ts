import type { Glossary, GlossaryEntry, HandCard, PilesView, PlayStep, PreviewResult, PressagioView } from "../types";

/** SPEC-334: lógica PURA da mão/fila do Baralho de Conflito (sem React; o motor revalida tudo). */

export const MAX_PLAYS = 8; // teto de `jogadas` na API (SPEC-328 R13)

export interface QueuedPlay {
  uid: string;
  cardId: string;
  name: string;
  targetId?: string;
  folego: number;
  entropia: number;
}

export interface FolegoState {
  spent: number;      // Fôlego pedido pela fila
  free: number;       // pips próprios ainda livres depois da fila
  borrowed: number;   // Fôlego "emprestado" (Pacto do Abismo) que a fila exige
  room: number;       // quanto do Pacto ainda cabe
}

export function folegoState(piles: Pick<PilesView, "folego" | "folego_emprestado" | "pacto_max">, queue: QueuedPlay[]): FolegoState {
  const spent = queue.reduce((n, p) => n + p.folego, 0);
  const own = Math.max(0, piles.folego);
  return {
    spent,
    free: Math.max(0, own - spent),
    borrowed: Math.max(0, spent - own),
    room: Math.max(0, piles.pacto_max - piles.folego_emprestado),
  };
}

export type BlockReason = "fardo" | "sem_folego" | "limite" | "ja_na_fila" | "entropia" | null;
export const BLOCK_TEXT: Record<Exclude<BlockReason, null>, string> = {
  fardo: "Fardo: não pode ser jogada",
  sem_folego: "Sem Fôlego",
  limite: "Fila cheia",
  ja_na_fila: "Já está na fila",
  entropia: "Entropia insuficiente",
};

/** Por que esta carta (cópia `index` da mão) não pode entrar na fila agora. */
export function blockReason(card: HandCard, hand: HandCard[], index: number, queue: QueuedPlay[],
  piles: PilesView, entropy: number | null): BlockReason {
  if (!card.jogavel) return "fardo";
  if (queue.length >= MAX_PLAYS) return "limite";
  const copiesBefore = hand.slice(0, index + 1).filter((c) => c.id === card.id).length;
  if (queue.filter((p) => p.cardId === card.id).length >= copiesBefore) return "ja_na_fila";
  const st = folegoState(piles, queue);
  if (card.custo_folego > st.free + st.room - st.borrowed) return "sem_folego";
  const entropyQueued = queue.reduce((n, p) => n + p.entropia, 0);
  if (entropy !== null && card.custo_entropia + entropyQueued > entropy) return "entropia";
  return null;
}

export function enqueue(queue: QueuedPlay[], card: HandCard, targetId: string | undefined, uid: string): QueuedPlay[] {
  return [...queue, { uid, cardId: card.id, name: card.name, targetId, folego: card.custo_folego, entropia: card.custo_entropia }];
}

export const remove = (queue: QueuedPlay[], uid: string) => queue.filter((p) => p.uid !== uid);

export function move(queue: QueuedPlay[], uid: string, delta: -1 | 1): QueuedPlay[] {
  const i = queue.findIndex((p) => p.uid === uid), j = i + delta;
  if (i < 0 || j < 0 || j >= queue.length) return queue;
  const next = [...queue];
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

/** A fila vira a lista `jogadas` do request único ("Encerrar turno"), na ordem escolhida. */
export function toJogadas(queue: QueuedPlay[]): PlayStep[] {
  return queue.map((p) => ({ card_id: p.cardId, ...(p.targetId ? { target_id: p.targetId } : {}) }));
}

/** Palavras-chave: `**Nome**` no texto gerado pelo servidor; `tip` casa com o glossário pelo nome. */
export interface RuleSegment { text: string; bold: boolean; tip?: GlossaryEntry }

export function ruleSegments(texto: string, glossary: Glossary): RuleSegment[] {
  const byName = new Map(Object.values(glossary).map((g) => [g.nome.toLowerCase(), g]));
  return texto.split(/(\*\*[^*]+\*\*)/).filter(Boolean).map((part) => {
    const m = /^\*\*([^*]+)\*\*$/.exec(part);
    if (!m) return { text: part, bold: false };
    return { text: m[1], bold: true, tip: byName.get(m[1].toLowerCase()) };
  });
}

/** Regras das palavras-chave do texto, para leitor de tela (sem depender de hover). */
export function keywordRules(texto: string, glossary: Glossary): string[] {
  return ruleSegments(texto, glossary).filter((s) => s.tip).map((s) => `${s.tip!.nome}: ${s.tip!.regra}`);
}

const fmtPct = (n: number) => `${Number.isInteger(n) ? n : n.toFixed(1).replace(".", ",")} %`;

/** "55 % · 4–7 de dano · pode Sangrar" — só o lado do jogador (nunca defesa oculta do alvo). */
export function previewLine(p: PreviewResult): string {
  const parts = [fmtPct(p.chance_acerto_pct)];
  if (p.dano_max > 0) parts.push(p.dano_min === p.dano_max ? `${p.dano_min} de dano` : `${p.dano_min}–${p.dano_max} de dano`);
  if (p.ferimento_provavel) parts.push(`ferimento ${p.ferimento_provavel} provável`);
  if (p.efeitos_extra.includes("Sangramento")) parts.push("pode Sangrar");
  if (p.pressagio_frustrado) parts.push("frustra o presságio");
  return parts.join(" · ");
}

/** Linha do presságio: o sinal do catálogo + a faixa/valor só quando o jogador já sabe lê-lo. */
export function pressagioLine(p: PressagioView, nameOf: (id: string) => string | undefined): string {
  const who = nameOf(p.actor_id) ?? "Inimigo";
  const num = p.valor_estimado !== null ? ` (~${p.valor_estimado})` : p.faixa ? ` (${p.faixa[0]}–${p.faixa[1]})` : "";
  const card = p.carta_nome ? ` — ${p.carta_nome}` : "";
  return `${who}: ${p.sinal}${card}${num}`;
}
