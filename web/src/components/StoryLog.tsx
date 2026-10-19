import { Fragment, memo, useEffect, useLayoutEffect, useRef, useState } from "react";
import { mdLite, roleLabel } from "../lib";
import { useTypewriter } from "../hooks/useTypewriter";
import type { LogEntry } from "../types";
import { VisualArtwork } from "./VisualArtwork";
import { shards } from "./AccountScreen";

/** Distância (px) do fim considerada "no fim" para o auto-scroll (SPEC-204 R7). */
const BOTTOM_SLACK = 48;

/** Memoizado (SPEC-204): trocar aba/modo/ratio re-renderiza o Workspace, não a narrativa. */
export const StoryLog = memo(function StoryLog({ entries, thinking, thinkingLabel, active = true, initialScroll, onScrollPosition }: {
  entries: LogEntry[];
  thinking: boolean;
  thinkingLabel?: string | null;
  /** Falso quando a superfície do chat está oculta (modo só-contexto). */
  active?: boolean;
  initialScroll?: { scrollTop: number | null; atBottom: boolean };
  onScrollPosition?: (scrollTop: number, atBottom: boolean) => void;
}) {
  const storyRef = useRef<HTMLElement>(null);
  const position = useRef({ top: initialScroll?.scrollTop ?? null, atBottom: initialScroll?.atBottom ?? true });
  const lastEntryId = useRef<number | null>(null);
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
    onScrollPosition?.(s.scrollTop, atBottom);
  }

  const streaming = entries.some((entry) => entry.streaming);

  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- região rolável precisa ser focável por teclado (WCAG 2.1.1)
    <section className="story" aria-label="Narrativa" ref={storyRef} tabIndex={0} onScroll={onScroll}>
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
              <LogEntryItem entry={e} />
            </Fragment>
          );
        })}
      </div>
      {thinking && (
        <div className="thinking" aria-live="polite">
          <span className="thinking__dot" />
          <span className="thinking__dot" />
          <span className="thinking__dot" />
          <span className="thinking__label">{thinkingLabel || "o narrador tece o destino…"}</span>
        </div>
      )}
    </section>
  );
});

function LogEntryItem({ entry }: { entry: LogEntry }) {
  const displayedText = useTypewriter(entry.text, entry.streaming, entry.onTypewriterDone);
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
    <article className={"msg msg--" + (entry.role === "player" ? "player" : entry.type.toLowerCase())}>
      {entry.visual && <VisualArtwork asset={entry.visual.asset}
        name={entry.visual.subject_name} caption={entry.visual.caption}
        className="msg__visual" />}
      {showRole && <p className="msg__role">{roleLabel(entry.role, entry.type, entry.speaker)}</p>}
      <div
        className="msg__body"
        dangerouslySetInnerHTML={{ __html: mdLite(displayedText) }}
      />
      {entry.streaming && <span className="msg__cursor" />}
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
