import { useEffect, useMemo, useRef, useState } from "react";
import type { CombatBlock, Glossary, HandCard } from "../../types";
import * as api from "../../api";
import { blockReason, enqueue, folegoState, move, remove, toJogadas, type QueuedPlay } from "../../combat/deck";
import { EnemyStrip } from "./EnemyStrip";
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

/** SPEC-334: o combate do Baralho (atrás da flag: só existe quando `combat.pilhas` chega).
 *  Faixa de presságios → Fôlego → mão → [alvo → prévia → jogar] → fila → "Encerrar turno" (1 request). */
export function DeckCombat({ combat, gameId, entropy, busy, touch, nameOf, onEnd, onAnnounce }: {
  combat: CombatBlock;
  gameId: string | null;
  entropy: number | null;
  busy: boolean;
  touch: boolean;
  nameOf: (id: string) => string | undefined;
  onEnd: (text: string, jogadas: ReturnType<typeof toJogadas>) => void;
  onAnnounce: (text: string) => void;
}) {
  const piles = combat.pilhas!;
  const [glossary, setGlossary] = useState<Glossary>({});
  const [queue, setQueue] = useState<QueuedPlay[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [armed, setArmed] = useState<{ index: number; targetId?: string } | null>(null);
  const [preview, setPreview] = useState<PreviewState>({ status: "idle" });
  const trigger = useRef<HTMLElement | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => { let alive = true; void api.getGlossary().then((g) => { if (alive) setGlossary(g); }); return () => { alive = false; }; }, []);
  // Nova rodada (mão nova): a fila antiga não vale mais.
  const roundKey = `${combat.round}|${piles.mao.map((c) => c.id).join(",")}`;
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
    setQueue([]); setSelected(null); setArmed(null);
  }, [roundKey]);

  const enemyIds = useMemo(() => combat.enemies.map((e) => e.id), [combat.enemies]);
  const reasons = piles.mao.map((c, i) => blockReason(c, piles.mao, i, queue, piles, entropy));
  const fol = folegoState(piles, queue);
  const armedCard: HandCard | null = armed ? piles.mao[armed.index] ?? null : null;
  const targetsFor = (card: HandCard): string[] => {
    const known = combat.cards.find((c) => c.id === card.id)?.valid_targets;
    return known ?? (card.alvo === "aliado" ? [] : enemyIds);
  };

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

  function play(card: HandCard, index: number, el?: HTMLElement) {
    if (el) trigger.current = el;
    const reason = reasons[index];
    if (reason) { onAnnounce(`${card.name}: indisponível.`); return; }
    if (armed?.index === index) { setArmed(null); return; } // 2º toque desarma
    if (card.alvo === "aliado") { playAlly(card, index); return; }
    if (card.alvo !== "inimigo") { add(card); return; }
    const targets = targetsFor(card);
    if (!targets.length) { onAnnounce(`${card.name}: sem alvo válido.`); return; }
    setArmed({ index, targetId: targets.length === 1 ? targets[0] : undefined });
  }

  function playAlly(card: HandCard, index: number) {
    // Suporte que mira aliado: 0–1 alvo conhecido → direto; vários → escolhe (sem prévia).
    const targets = combat.cards.find((c) => c.id === card.id)?.valid_targets ?? [];
    if (targets.length <= 1) { add(card, targets[0]); return; }
    setArmed({ index });
  }

  function add(card: HandCard, targetId?: string) {
    setQueue((q) => enqueue(q, card, targetId, `p${++uidSeq}`));
    setArmed(null);
    onAnnounce(`${card.name} entrou na fila.`);
    trigger.current?.focus();
  }

  const end = () => { if (!busy && queue.length) onEnd(`Encerrar turno: ${queue.map((p) => p.name).join(", ")}.`, toJogadas(queue)); };

  // Atalhos (R8): 1–5 cartas · Enter encerra · Esc desarma/limpa. Ignorados ao digitar ou sobre botões.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || busy || event.ctrlKey || event.metaKey || event.altKey || isTyping(event.target)) return;
      if (document.querySelector("[aria-modal='true'], dialog[open]")) return; // modal aberto: o atalho não é do combate
      if (/^[1-5]$/.test(event.key)) {
        const index = Number(event.key) - 1, card = piles.mao[index];
        if (card) { event.preventDefault(); play(card, index, rootRef.current?.querySelectorAll<HTMLElement>(".deck-card")[index]); }
      } else if (event.key === "Enter" && !(event.target as HTMLElement | null)?.closest?.("button, summary, a, [role=button], [role=tab], [tabindex]")) {
        if (queue.length) { event.preventDefault(); end(); }
      } else if (event.key === "Escape") {
        if (armed) { event.preventDefault(); setArmed(null); trigger.current?.focus(); }
        else if (queue.length) { event.preventDefault(); setQueue([]); setSelected(null); onAnnounce("Fila limpa."); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  return (
    <div className="deck-combat" ref={rootRef} data-aim-safe>
      <SceneStrip round={combat.round} />
      <EnemyStrip pressagios={combat.pressagios_publicos ?? []} nameOf={nameOf} />
      <FolegoPips piles={piles} state={fol} />
      <Hand piles={piles} glossary={glossary} reasons={reasons} armedIndex={armed?.index ?? null} busy={busy} onPlay={play} />
      {armedCard && (
        <div className="deck-target" role="group" aria-label={`Alvo de ${armedCard.name}`}>
          {armed?.targetId === undefined ? (
            <>
              <span>Alvo:</span>
              {targetsFor(armedCard).map((id) => (
                <button key={id} type="button" className="actionchip" data-target-pick={id}
                  onClick={() => { if (armedCard.alvo === "aliado") add(armedCard, id); else setArmed({ index: armed!.index, targetId: id }); }}>{nameOf(id) ?? id}</button>
              ))}
            </>
          ) : (
            <>
              <PreviewChip state={preview} />
              <button type="button" className="actionchip" data-play-confirm onClick={() => add(armedCard, armed.targetId)}>
                Jogar em {nameOf(armed.targetId) ?? "alvo"}
              </button>
              {targetsFor(armedCard).length > 1 && (
                <button type="button" className="actionchip" onClick={() => setArmed({ index: armed.index })}>Outro alvo</button>
              )}
            </>
          )}
        </div>
      )}
      <PlayQueue queue={queue} selected={selected} nameOf={nameOf} busy={busy} touch={touch}
        onSelect={setSelected} onMove={(uid, d) => setQueue((q) => move(q, uid, d))}
        onRemove={(uid) => { setQueue((q) => remove(q, uid)); setSelected(null); }}
        onClear={() => { setQueue([]); setSelected(null); }} onEnd={end} />
      <MechLog lines={combat.mech_log ?? []} />
    </div>
  );
}
