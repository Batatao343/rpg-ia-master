import type { Glossary, GlossaryEntry, HandCard, OmenView, PilesView, PlayStep, PreviewResult, PressagioView, SceneCardsView, SceneObjectiveView } from "../types";
import type { IconName } from "../design/icons";

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
  fardo: "Fardo: pesa na mão, não se joga",
  sem_folego: "Falta fôlego",
  limite: "Não cabe mais nada nesta rodada",
  ja_na_fila: "Já vai na fila",
  entropia: "A Entropia não basta",
};

/** SPEC-342 R10.2: marginália enviada (1ª pessoa). O servidor não depende deste texto: a semântica vem de `jogadas`.
 *  `Sem matar.` é a frase que `death_flow.NONLETHAL_RE` reconhece. */
export const SPARE_SENTENCE = "Sem matar.";
export function endText(queue: QueuedPlay[], spare: boolean): string {
  return `Encerro a rodada: ${queue.map((p) => p.name).join(", ")}.${spare ? ` ${SPARE_SENTENCE}` : ""}`;
}

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

/** SPEC-347 R10: percentual inteiro; só 0 e 100 são exatos — o que não é certo nunca mostra "0 %"/"100 %". */
export function fmtPct(n: number): string {
  const v = n <= 0 ? 0 : n >= 100 ? 100 : Math.min(99, Math.max(1, Math.round(n)));
  return `${v} %`;
}

/** SPEC-342 R7.1: a chance (número em destaque) separada do resto da linha da prévia. */
export function previewParts(p: PreviewResult): { chance: string; rest: string } {
  const [chance, ...rest] = previewLine(p).split(" · ");
  return { chance, rest: rest.join(" · ") };
}

/** "55 % · 4–7 de dano · pode Sangrar" — só o lado do jogador (nunca defesa oculta do alvo). */
export function previewLine(p: PreviewResult): string {
  const parts = [(p.aproximado ? "≈ " : "") + fmtPct(p.chance_acerto_pct)];
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

/** SPEC-342 R8: tipos de presságio (`services/enemy_intent.py::TIPOS`) → ícone que já existe em `design/icons`. */
export const TIPOS = ["ataque", "ataque_multiplo", "defesa", "reforco_proprio", "enfraquecer", "mover", "fugir", "render-se", "desconhecido"] as const;
export const OMEN_ICON: Record<(typeof TIPOS)[number], IconName> = {
  ataque: "card-active", ataque_multiplo: "combat", defesa: "card-reaction", reforco_proprio: "card-passive",
  enfraquecer: "warning", mover: "arrow-right", fugir: "exit", "render-se": "blocked", desconhecido: "dark",
};
export const VEILED_TEXT = "Intenção velada";

/** `p` nulo (inimigo sem entrada com a flag de intenção ligada) ou `desconhecido` → velada (R8.3). */
export function omenView(p: PressagioView | null, name: string): OmenView {
  if (!p || p.tipo === "desconhecido") {
    return { icon: "dark", text: VEILED_TEXT, num: null, card: null, veiled: true, spoken: `${name}: ${VEILED_TEXT}` };
  }
  const num = p.valor_estimado !== null ? `~${p.valor_estimado}` : p.faixa ? `${p.faixa[0]}–${p.faixa[1]}` : null;
  const icon = (OMEN_ICON as Record<string, IconName>)[p.tipo] ?? "dark";
  const spoken = `${p.sinal.startsWith(name) ? "" : `${name}: `}${p.sinal}${p.carta_nome ? ` — ${p.carta_nome}` : ""}${num ? ` (${num})` : ""}`;
  return { icon, text: p.sinal, num, card: p.carta_nome, veiled: false, spoken };
}

/** SPEC-342 R2.3: objetivo da cena por extenso (strings da D-342-7). */
export function objectiveLine(o: SceneObjectiveView): string {
  if (o.resultado === "cumprido") return "Objetivo cumprido";
  if (o.resultado === "falhou") return "Objetivo perdido";
  const alvo = o.alvo_nome ?? "o alvo";
  const n = o.n ?? 0;
  switch (o.tipo) {
    case "sobreviver_n_rodadas": return `Resista até a rodada ${n} (faltam ${Math.max(0, n - o.rodada)})`;
    case "proteger": return `Mantenha ${alvo} de pé`;
    case "alcancar_zona": return `Alcance ${alvo}`;
    case "destruir_objeto": return `Destrua ${alvo}`;
    case "interromper_ritual": return `Derrube ${alvo} antes da rodada ${n}, ou o ritual se completa`;
    case "capturar_vivo": return 'Leve-os vivos (use "Sem matar")';
    default: return "";
  }
}

export function clockLine(r: SceneCardsView["relogio"]): string {
  return r.ativo ? "O Abismo se aproxima: +1 Carga por rodada" : `Relógio do Abismo: desperta na rodada ${r.desde}`;
}
export const clockBody = (r: SceneCardsView["relogio"]) =>
  `Da rodada ${r.desde} em diante, quem carrega o Abismo ganha +1 Carga a cada rodada e a cena mais forte volta a agir. Na rodada ${r.teto}, os inimigos recuam diante do Abismo.`;

/** SPEC-342 R3.2: alvos válidos de uma carta da mão. O servidor manda `valid_targets` quando conhece a carta; sem isso,
 *  carta de aliado mira o jogador e o grupo e a de inimigo, os inimigos. `si` não tem alvo. */
export function cardTargets(card: HandCard, known: string[] | undefined, enemyIds: string[], friendIds: string[]): string[] {
  if (card.alvo === "si") return [];
  if (known) return known;
  return card.alvo === "aliado" ? friendIds : enemyIds;
}
