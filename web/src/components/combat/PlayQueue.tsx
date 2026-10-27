import { Icon } from "../../design/icons";
import type { QueuedPlay } from "../../combat/deck";

/** SPEC-334 R5/R8: fila local (sem request) reordenável e cancelável. O item selecionado mostra ↑ ↓ ✕
 *  (poucos controles à vista, R7). Enter encerra o turno e Esc limpa — ligados pelo contêiner. */
export function PlayQueue({ queue, selected, nameOf, busy, onSelect, onMove, onRemove, onClear, onEnd, touch }: {
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
}) {
  return (
    <section className="play-queue" aria-label="Fila de jogadas" data-aim-safe>
      {queue.length === 0 ? (
        <p className="play-queue__empty">Escolha cartas da mão: elas entram na fila e só valem ao encerrar o turno.</p>
      ) : (
        <ol className="play-queue__list">
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
                    <button type="button" aria-label={`Cancelar ${p.name}`} disabled={busy} onClick={() => onRemove(p.uid)}><Icon name="close" /></button>
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      )}
      <div className="play-queue__end">
        <button type="button" className="play-queue__submit" data-end-turn disabled={busy || queue.length === 0}
          aria-keyshortcuts="Enter" onClick={onEnd}>
          Encerrar turno{queue.length ? ` (${queue.length})` : ""}
        </button>
        {queue.length > 0 && (
          <button type="button" className="play-queue__clear" disabled={busy} aria-keyshortcuts="Escape" onClick={onClear}>
            {touch ? "Limpar fila" : "Limpar (Esc)"}
          </button>
        )}
      </div>
    </section>
  );
}
