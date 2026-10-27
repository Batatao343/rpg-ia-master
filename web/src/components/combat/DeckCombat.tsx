import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { CombatBlock, HandCard, OmenView } from "../../types";
import * as api from "../../api";
import { BLOCK_TEXT, blockReason, cardTargets, endText, enqueue, folegoState, keywordRules, move, omenView, remove, toJogadas, type QueuedPlay } from "../../combat/deck";
import type { DeckArm } from "../../combat/useDeckArm";
import { useGlossary } from "../../combat/useGlossary";
import { FolegoPips } from "./FolegoPips";
import { Hand } from "./Hand";
import { MechLog } from "./MechLog";
import { PlayQueue } from "./PlayQueue";
import { PreviewChip, type PreviewState } from "./PreviewChip";
import { SceneStrip } from "./SceneStrip";

const isTyping = (el: EventTarget | null) => {
  const node = el as HTMLElement | null;
  return !!node && (node.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(node.tagName));
};
let uidSeq = 0;

/** SPEC-334 + SPEC-342: o combate do Baralho (atrás da flag: só existe quando `combat.pilhas` chega).
 *  Faixa de cena → Arena (único seletor de alvo, vem em `arena`) → mão → [mira → prévia → jogar] → fila → "Encerrar a rodada".
 *  A carta armada vive no contêiner (`armed`), porque a Arena marca os alvos válidos; a fila é local. */
export function DeckCombat({ combat, gameId, entropy, busy, touch, nameOf, onEnd, onAnnounce, arena, maneuverAim, friendIds, armed, onArm, onDisarm, onClearTarget, spareAvailable, spare, onSpare, onStuck }: {
  combat: CombatBlock;
  gameId: string | null;
  entropy: number | null;
  busy: boolean;
  touch: boolean;
  nameOf: (id: string) => string | undefined;
  onEnd: (text: string, jogadas: ReturnType<typeof toJogadas>) => void;
  onAnnounce: (text: string) => void;
  /** Render prop da Arena (o presságio mora no chip do inimigo, R8). */
  arena: (omens?: Record<string, OmenView>) => ReactNode;
  /** Barra de mira da manobra (exclusiva com a da carta). */
  maneuverAim?: ReactNode;
  friendIds: string[];
  armed: DeckArm | null;
  onArm: (index: number, targets: string[]) => void;
  onDisarm: () => void;
  onClearTarget: () => void;
  spareAvailable: boolean;
  spare: boolean;
  onSpare: () => void;
  onStuck?: (stuck: boolean) => void;
}) {
  const piles = combat.pilhas!;
  const glossary = useGlossary();
  const [queue, setQueue] = useState<QueuedPlay[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewState>({ status: "idle" });
  const trigger = useRef<HTMLElement | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  // Nova rodada (mão nova): a fila antiga não vale mais. O foco só vai à 1ª carta se já estava aqui dentro (R15.4).
  const roundKey = `${combat.round}|${piles.mao.map((c) => c.id).join(",")}`;
  const firstRound = useRef(true);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
    setQueue([]); setSelected(null); onDisarm();
    if (firstRound.current) { firstRound.current = false; return; }
    const root = rootRef.current;
    if (root && root.contains(document.activeElement)) root.querySelector<HTMLElement>(".deck-card")?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roundKey]);

  const enemyIds = useMemo(() => combat.enemies.map((e) => e.id), [combat.enemies]);
  const reasons = piles.mao.map((c, i) => blockReason(c, piles.mao, i, queue, piles, entropy));
  const fol = folegoState(piles, queue);
  const armedCard: HandCard | null = armed ? piles.mao[armed.index] ?? null : null;
  const targetsFor = (card: HandCard): string[] =>
    cardTargets(card, combat.cards.find((c) => c.id === card.id)?.valid_targets, enemyIds, friendIds);
  const needsTarget = !!armedCard && armedCard.alvo !== "si";
  const armedTargets = armedCard ? targetsFor(armedCard) : [];

  // Presságio dentro do chip do inimigo (R8). Com a flag de intenção ligada, quem não tem entrada fica "velado".
  const omens = useMemo<Record<string, OmenView> | undefined>(() => {
    const list = combat.pressagios_publicos;
    if (!list) return undefined;
    return Object.fromEntries(combat.enemies.map((e) => [e.id, omenView(list.find((p) => p.actor_id === e.id) ?? null, nameOf(e.id) ?? e.name)]));
  }, [combat.pressagios_publicos, combat.enemies, nameOf]);

  // Prévia: só com carta + alvo escolhidos; cancela a anterior (sem round-trip pendente).
  const previewKey = armedCard?.alvo === "inimigo" && armed?.targetId ? `${armedCard.id}|${armed.targetId}` : "";
  useEffect(() => {
    if (!previewKey || !armedCard || !armed?.targetId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
      setPreview({ status: "idle" });
      return;
    }
    const ctl = new AbortController();
    setPreview({ status: "loading" });
    api.previewPlay(gameId, armedCard.id, armed.targetId, ctl.signal)
      .then((result) => setPreview({ status: "ok", result }))
      .catch(() => { if (!ctl.signal.aborted) setPreview({ status: "error" }); });
    return () => ctl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewKey, gameId]);

  // Foco (R15.1): alvo já fixado (1 alvo, ou escolhido na Arena) → "Jogar em X". Sem alvo, o contêiner foca a Arena.
  const confirmKey = armed && (armed.targetId || !needsTarget) ? `${armed.index}|${armed.targetId ?? ""}` : "";
  useEffect(() => {
    if (confirmKey) rootRef.current?.querySelector<HTMLElement>("[data-play-confirm]")?.focus();
  }, [confirmKey]);

  function disarm() {
    onDisarm();
    trigger.current?.focus();
  }

  function play(card: HandCard, index: number, el?: HTMLElement) {
    if (el) trigger.current = el;
    const reason = reasons[index];
    if (reason) { onAnnounce(`${card.name}: ${BLOCK_TEXT[reason]}.`); return; }
    if (armed?.index === index) { disarm(); return; } // 2º toque desarma
    if (card.alvo === "si") {
      if (touch) { onArm(index, []); return; } // toque: arma, mostra o texto e as regras, e "Jogar" confirma (R9.1)
      add(card);
      return;
    }
    const targets = targetsFor(card);
    if (!targets.length) { onAnnounce(`${card.name}: ninguém ao alcance.`); return; }
    onArm(index, targets);
    onAnnounce(targets.length > 1 ? `Mirando ${card.name}: escolha o alvo na arena.` : "");
  }

  function add(card: HandCard, targetId?: string) {
    const n = queue.length + 1;
    setQueue((q) => enqueue(q, card, targetId, `p${++uidSeq}`));
    onDisarm();
    onAnnounce(`${card.name} vai na fila, em ${n}º.`);
    trigger.current?.focus();
  }

  const end = () => { if (!busy && queue.length) onEnd(endText(queue, spare), toJogadas(queue)); };

  // Atalhos (R8): 1–5 cartas · Enter encerra · Esc desarma/desfaz. Ignorados ao digitar, sobre botões e com a aba oculta (R18.1).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || busy || event.ctrlKey || event.metaKey || event.altKey || isTyping(event.target)) return;
      const root = rootRef.current;
      if (!root || root.closest("[hidden]") || root.offsetParent === null) return;
      if (document.querySelector("[aria-modal='true'], dialog[open]")) return; // modal aberto: o atalho não é do combate
      if (/^[1-5]$/.test(event.key)) {
        const index = Number(event.key) - 1, card = piles.mao[index];
        if (card) { event.preventDefault(); play(card, index, root.querySelectorAll<HTMLElement>(".deck-card")[index]); }
      } else if (event.key === "Enter" && !(event.target as HTMLElement | null)?.closest?.("button, summary, a, [role=button], [role=tab], [tabindex]")) {
        if (queue.length) { event.preventDefault(); end(); }
      } else if (event.key === "Escape") {
        if (armed) { event.preventDefault(); disarm(); }
        else if (queue.length) { event.preventDefault(); setQueue([]); setSelected(null); onAnnounce("Fila desfeita."); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const rules = armedCard && touch ? keywordRules(armedCard.texto ?? "", glossary) : [];
  return (
    <div className="deck-combat" ref={rootRef} data-aim-safe data-omens={omens ? "on" : undefined}>
      <SceneStrip round={combat.round} cena={combat.cena} objetivo={combat.objetivo} pressagios={combat.pressagios_cena} />
      {arena(omens)}
      <Hand piles={piles} glossary={glossary} reasons={reasons} armedIndex={armed?.index ?? null} busy={busy} onPlay={play}
        head={<FolegoPips piles={piles} state={fol} />} onStuck={onStuck} />
      {armedCard ? (
        <div className="aimbar" data-aim-safe data-deck-aim role="group" aria-label={`Mira de ${armedCard.name}`}>
          {needsTarget && !armed?.targetId ? (
            <span>Mirando {armedCard.name}: escolha o alvo na arena.</span>
          ) : (
            <>
              <PreviewChip state={preview} />
              <button type="button" className="btn btn--primary btn--sm" data-play-confirm
                onClick={() => add(armedCard, armed?.targetId)}>
                {armed?.targetId ? `Jogar em ${nameOf(armed.targetId) ?? "alvo"}` : "Jogar"}
              </button>
              {needsTarget && armedTargets.length > 1 && (
                <button type="button" className="actionchip" data-other-target onClick={onClearTarget}>Outro alvo</button>
              )}
            </>
          )}
          {touch && (
            <div className="aimbar__rules" data-card-rules>
              {armedCard.texto && <p>{armedCard.texto.replace(/\*\*/g, "")}</p>}
              {rules.map((r) => {
                const at = r.indexOf(": ");
                return <p key={r}><strong>{r.slice(0, at)}</strong>: {r.slice(at + 2)}</p>;
              })}
            </div>
          )}
          <button type="button" className="aimbar__cancel" onClick={disarm}>{touch ? "Cancelar" : "Cancelar (Esc)"}</button>
        </div>
      ) : maneuverAim}
      <PlayQueue queue={queue} selected={selected} nameOf={nameOf} busy={busy} touch={touch}
        onSelect={setSelected} onMove={(uid, d) => setQueue((q) => move(q, uid, d))}
        onRemove={(uid) => { setQueue((q) => remove(q, uid)); setSelected(null); }}
        onClear={() => { setQueue([]); setSelected(null); }} onEnd={end}
        spareAvailable={spareAvailable} spare={spare} onSpare={onSpare}
        firstCardFocus={() => rootRef.current?.querySelector<HTMLElement>(".deck-card")?.focus()} />
      <MechLog lines={combat.mech_log ?? []} round={combat.round} />
    </div>
  );
}
