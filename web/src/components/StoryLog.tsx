import { Fragment, memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { mdLite, roleLabel } from "../lib";
import { useTypewriter } from "../hooks/useTypewriter";
import { useEffectsEnabled } from "../design/motion";
import { htmlToPlain, revealHtml } from "../revealHtml";
import { openingAllowed } from "../turnWait";
import type { GameResponse, LogEntry } from "../types";
import { VisualArtwork } from "./VisualArtwork";
import { shards } from "./AccountScreen";

/** Distância (px) do fim considerada "no fim" para o auto-scroll (SPEC-204 R7). */
const BOTTOM_SLACK = 48;

/** Memoizado (SPEC-204): trocar aba/modo/ratio re-renderiza o Workspace, não a narrativa. */
export const StoryLog = memo(function StoryLog({ entries, thinking, active = true, initialScroll, onScrollPosition, offers, onOffer, offersDisabled }: {
  entries: LogEntry[];
  thinking: boolean;
  /** Falso quando a superfície do chat está oculta (modo só-contexto). */
  active?: boolean;
  initialScroll?: { scrollTop: number | null; atBottom: boolean };
  /** `byUser`: o scroll veio de gesto (roda/toque/teclado) — não do auto-scroll para o fim. */
  onScrollPosition?: (scrollTop: number, atBottom: boolean, byUser?: boolean) => void;
  /** SPEC-321 R6: ofertas de arte de cena/NPC viram um chip na narração mais recente (não ficam no topo). */
  offers?: NonNullable<GameResponse["art_offers"]>;
  onOffer?: (offer: NonNullable<GameResponse["art_offers"]>[number]) => void;
  offersDisabled?: boolean;
}) {
  const storyRef = useRef<HTMLElement>(null);
  const position = useRef({ top: initialScroll?.scrollTop ?? null, atBottom: initialScroll?.atBottom ?? true });
  const lastEntryId = useRef<number | null>(null);
  const lastGesture = useRef(0);
  const markGesture = () => { lastGesture.current = Date.now(); };
  // M09 (SPEC-208): nenhuma entrada anima — nem histórico/reload nem o bloco novo (o typewriter e o
  // cursor já mostram o que chega). A fade do bloco novo foi medida e REJEITADA: sob CPU 4x somava ~1
  // vsync ao p95 de frame do fluxo de chat (docs/spec208/README.md). Sem `filter`/`blur` em lista.

  // Restaura a posição ao montar e sempre que a superfície volta a aparecer.
  useLayoutEffect(() => {
    const s = storyRef.current;
    if (!s || !active) return;
    s.scrollTop = position.current.atBottom || position.current.top == null ? s.scrollHeight : position.current.top;
  }, [active]);

  // Auto-scroll só quando o jogador já está no fim ou acabou de agir.
  useEffect(() => {
    const s = storyRef.current;
    const last = entries[entries.length - 1];
    const ownNew = !!last && last.role === "player" && last.id !== lastEntryId.current;
    lastEntryId.current = last?.id ?? null;
    if (!s || !active) return;
    if (position.current.atBottom || ownNew) {
      s.scrollTop = s.scrollHeight;
      position.current = { top: s.scrollTop, atBottom: true };
    }
  }, [entries, thinking, active]);

  function onScroll() {
    const s = storyRef.current;
    if (!s || !active || s.clientHeight === 0) return;
    const atBottom = s.scrollHeight - s.scrollTop - s.clientHeight <= BOTTOM_SLACK;
    position.current = { top: s.scrollTop, atBottom };
    onScrollPosition?.(s.scrollTop, atBottom, Date.now() - lastGesture.current < 1000);
  }

  const streaming = entries.some((entry) => entry.streaming);
  const lastNarrator = entries.reduce((idx, e, i) => (e.role === "narrator" ? i : idx), -1);
  const offerRow = (offers?.length ?? 0) > 0 && onOffer ? (
    <div className="msg__offers">
      {offers!.map((offer) => (
        <button key={offer.offer_id} type="button" className="msg__offer" disabled={offersDisabled}
          onClick={() => onOffer(offer)}>
          {offer.type === "npc" ? "Cotar retrato de NPC" : "Cotar cena épica"}
        </button>
      ))}
    </div>
  ) : null;

  // SPEC-320 R6: entradas em revelação se registram aqui; Esc/Espaço na região da história revela tudo.
  const revealers = useRef(new Map<number, () => void>());
  const registerReveal = useCallback((id: number, fn: (() => void) | null) => {
    if (fn) revealers.current.set(id, fn); else revealers.current.delete(id);
  }, []);
  function onKeyDown(e: KeyboardEvent<HTMLElement>) {
    markGesture();
    if (e.target !== e.currentTarget || (e.key !== "Escape" && e.key !== " ") || revealers.current.size === 0) return;
    e.preventDefault(); // Espaço não rola enquanto há algo a revelar
    [...revealers.current.values()].forEach(fn => fn());
  }

  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex, jsx-a11y/no-noninteractive-element-interactions -- região rolável focável por teclado (WCAG 2.1.1); Esc/Espaço revelam o texto (SPEC-320 R6)
    <section className="story" aria-label="Narrativa" ref={storyRef} tabIndex={0} onScroll={onScroll} onKeyDown={onKeyDown}
      onWheel={markGesture} onTouchMove={markGesture} onPointerDown={markGesture}>
      {/* SPEC-201 A08: um anúncio por bloco novo; aria-busy segura a leitura enquanto o texto escorre. */}
      <div className="log" role="log" aria-live="polite" aria-relevant="additions" aria-busy={streaming || thinking}>
        {entries.map((e, i) => {
          const prev = entries[i - 1];
          // Fleuron entre dois turnos de narração seguidos: separa beats como
          // num diário, sem o rótulo repetido "Narrador" (ref: livro, não chat).
          const sceneBreak = !!prev && prev.role === "narrator" && e.role === "narrator";
          return (
            <Fragment key={e.id}>
              {sceneBreak && (
                <div className="scene-break" aria-hidden>
                  <span>❧</span>
                </div>
              )}
              <LogEntryItem entry={e} registerReveal={registerReveal} />
              {i === lastNarrator && offerRow}
            </Fragment>
          );
        })}
        {lastNarrator < 0 && offerRow}
      </div>
    </section>
  );
});

function LogEntryItem({ entry, registerReveal }: { entry: LogEntry; registerReveal: (id: number, fn: (() => void) | null) => void }) {
  // R8: mdLite roda no máximo uma vez por texto recebido (chunk); a revelação só corta o HTML pronto.
  const html = useMemo(() => mdLite(entry.text), [entry.text]);
  const plain = useMemo(() => htmlToPlain(html), [html]);
  const effects = useEffectsEnabled();
  const { displayedText, reveal, revealing } = useTypewriter(plain, entry.streaming, entry.onTypewriterDone, { effects });
  useEffect(() => {
    registerReveal(entry.id, revealing ? reveal : null);
    return () => registerReveal(entry.id, null);
  }, [entry.id, revealing, reveal, registerReveal]);
  const shownHtml = displayedText.length >= plain.length ? html : revealHtml(html, displayedText.length);
  const [costOpen, setCostOpen] = useState(false);
  const technical = entry.technicalCostUsd && /[1-9]/.test(entry.technicalCostUsd)
    ? `${entry.technicalCostExact ? "Custo técnico registrado" : "Estimativa de custo técnico"}: US$ ${entry.technicalCostUsd.replace(".", ",")}`
    : null;
  const settled = entry.costMilli != null
    ? `Débito liquidado: ${shards(entry.costMilli)} Estilhas` : null;
  const costText = [technical, settled].filter(Boolean).join(" · ");

  // A narração é a voz padrão do diário — não carimba "Narrador" em todo bloco
  // (era um eyebrow repetido). Rótulo só quando muda o sentido: fala do jogador,
  // diálogo de NPC, combate, espólio.
  // SPEC-202: fala de NPC identificado sempre mostra o nome canônico (passivo).
  const showRole = entry.role === "player"
    || (entry.role === "narrator" && (entry.type !== "STORY" || entry.speaker?.kind === "npc"));

  return (
    // Toque/clique revela tudo (R6); o equivalente de teclado (Esc/Espaço) vive na região `.story`.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <article className={"msg msg--" + (entry.role === "player" ? "player" : entry.type.toLowerCase())}
      data-opening={entry.opening && entry.role === "narrator" && openingAllowed(entry.text, true) ? "" : undefined}
      onClick={revealing ? reveal : undefined}>
      {entry.visual && <VisualArtwork asset={entry.visual.asset}
        name={entry.visual.subject_name} caption={entry.visual.caption}
        className="msg__visual" />}
      {showRole && <p className="msg__role">{roleLabel(entry.role, entry.type, entry.speaker)}</p>}
      <div
        className="msg__body"
        dangerouslySetInnerHTML={{ __html: shownHtml }}
      />
      {entry.streaming && <span className="msg__cursor" />}
      {entry.unsaved && <span className="msg__unsaved">não salvo</span>}
      {entry.role === "narrator" && costText && !entry.streaming &&
        <span className="msg__cost">
          <button type="button" className="msg__cost-button" aria-expanded={costOpen}
            aria-controls={`cost-${entry.id}`}
            aria-label={`Custo deste turno. ${costText}`}
            onClick={() => setCostOpen(value => !value)}>✧</button>
          <span id={`cost-${entry.id}`} className={`msg__cost-detail${costOpen ? " is-open" : ""}`}>
            {costText}{!settled ? " · Sem débito em Estilhas" : ""}
          </span>
        </span>}
    </article>
  );
}
