import { useRef } from "react";
import { Icon } from "../../design/icons";
import type { QueuedPlay } from "../../combat/deck";

export const SPARE_NOTE = "Nesta rodada, golpes derrubam sem matar.";
export const QUEUE_EMPTY = "Escolha cartas da mão. Elas esperam aqui e só valem quando você encerrar a rodada.";

/** SPEC-334 R5/R8 + SPEC-342 R1.2/R7: fila local (sem request) reordenável e cancelável. A barra de envio leva
 *  "Sem matar" (quando existe), "Encerrar a rodada" (única ação primária da aba) e "Desfazer". Enter encerra e Esc
 *  desfaz — ligados pelo contêiner. */
export function PlayQueue({ queue, selected, nameOf, busy, onSelect, onMove, onRemove, onClear, onEnd, touch, spareAvailable = false, spare = false, onSpare, firstCardFocus }: {
  queue: QueuedPlay[];
  selected: string | null;
  nameOf: (id: string) => string | undefined;
  busy: boolean;
  onSelect: (uid: string | null) => void;
  onMove: (uid: string, delta: -1 | 1) => void;
  onRemove: (uid: string) => void;
  onClear: () => void;
  onEnd: () => void;
  touch: boolean;
  spareAvailable?: boolean;
  spare?: boolean;
  onSpare?: () => void;
  /** R15.3: fila esvaziou → foco na 1ª carta da mão. */
  firstCardFocus?: () => void;
}) {
  const listRef = useRef<HTMLOListElement>(null);
  // R15.3: remover move o foco para o item seguinte, o anterior, ou a 1ª carta da mão.
  function remove(uid: string, i: number) {
    const items = Array.from(listRef.current?.querySelectorAll<HTMLElement>(".play-queue__item") ?? []);
    const next = items[i + 1] ?? items[i - 1];
    onRemove(uid);
    window.setTimeout(() => { if (next && next.isConnected) next.focus(); else firstCardFocus?.(); }, 0);
  }
  return (
    <>
    <section className="play-queue" aria-label="Fila de jogadas" data-aim-safe>
      {queue.length === 0 ? (
        <p className="play-queue__empty">{QUEUE_EMPTY}</p>
      ) : (
        <ol className="play-queue__list" ref={listRef}>
          {queue.map((p, i) => {
            const open = selected === p.uid;
            return (
              <li key={p.uid} className={open ? "is-selected" : undefined}>
                <button type="button" className="play-queue__item" aria-expanded={open}
                  aria-label={`${i + 1}º: ${p.name}${p.targetId ? ` em ${nameOf(p.targetId) ?? "alvo"}` : ""}. ${open ? "Fechar opções" : "Abrir opções"}`}
                  onClick={() => onSelect(open ? null : p.uid)}>
                  <span className="play-queue__n">{i + 1}</span> {p.name}
                  {p.targetId && <span className="play-queue__to"> → {nameOf(p.targetId) ?? "alvo"}</span>}
                </button>
                {open && (
                  <span className="play-queue__ops">
                    <button type="button" aria-label={`Subir ${p.name}`} disabled={i === 0 || busy} onClick={() => onMove(p.uid, -1)}><Icon name="caret-up" /></button>
                    <button type="button" aria-label={`Descer ${p.name}`} disabled={i === queue.length - 1 || busy} onClick={() => onMove(p.uid, 1)}><Icon name="caret-down" /></button>
                    <button type="button" aria-label={`Cancelar ${p.name}`} disabled={busy} onClick={() => remove(p.uid, i)}><Icon name="close" /></button>
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      )}
      {spare && <p className="play-queue__spare" role="note">{SPARE_NOTE}</p>}
    </section>
    <div className="play-queue__end" data-aim-safe>
        {spareAvailable && (
          <button type="button" className="actionchip" data-spare aria-pressed={spare} onClick={onSpare}
            title="Os golpes desta rodada derrubam o alvo sem matá-lo (se a forma do ataque permitir).">
            Sem matar
          </button>
        )}
        <button type="button" className="btn btn--primary play-queue__submit" data-end-turn
          aria-disabled={busy || queue.length === 0 ? "true" : undefined}
          aria-keyshortcuts="Enter" title="Encerrar a rodada (Enter)"
          onClick={() => { if (!busy && queue.length) onEnd(); }}>
          <span>Encerrar a rodada</span>
          {queue.length > 0 && <small className="play-queue__count">{queue.length} {queue.length === 1 ? "carta" : "cartas"}</small>}
        </button>
        {queue.length > 0 && (
          <button type="button" className="btn btn--ghost btn--sm play-queue__clear" disabled={busy} aria-keyshortcuts="Escape" onClick={onClear}>
            {touch ? "Desfazer fila" : "Desfazer (Esc)"}
          </button>
        )}
    </div>
    </>
  );
}
