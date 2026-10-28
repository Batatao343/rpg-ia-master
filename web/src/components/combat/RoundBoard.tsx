import type { RoundLogEntry } from "../../types";
import { roundLogView } from "../../combat/deck";
import { Icon } from "../../design/icons";

const RECENT = 4;

function Row({ e }: { e: RoundLogEntry }) {
  const v = roundLogView(e);
  return (
    <li className={`roundboard__row roundboard__row--${e.lado}`} data-origem={e.origem}>
      <span className="roundboard__who">{e.lado === "heroi" ? <Icon name="combat" /> : null}<strong>{e.ator_id === "player" ? "Você" : v.who}</strong></span>
      <span className="roundboard__card" data-reacao={e.origem === "reacao" ? "" : undefined}>{v.card}</span>
      {v.to && <><span className="roundboard__arrow" aria-hidden="true">→</span><span className="roundboard__to">{v.to}</span></>}
      <span className={`roundboard__chip roundboard__chip--${v.tone}`}>{v.chip}</span>
    </li>
  );
}

/** SPEC-347 R14.3: o registro das cartas da última rodada resolvida, entre a faixa de cena e a Arena. Sem entradas não
 *  renderiza nada. No celular (`compact`) mostra as últimas 4 e "Ver a rodada inteira (N)"; no desktop, todas. */
export function RoundBoard({ entries, round, compact }: { entries: RoundLogEntry[] | undefined; round: number; compact: boolean }) {
  if (!entries || entries.length === 0) return null;
  const shown = compact ? entries.slice(-RECENT) : entries;
  return (
    <section className="roundboard" aria-label={`O que se jogou na rodada ${Math.max(1, round - 1)}`} data-roundboard>
      <h3 className="roundboard__title section-label">{`O que se jogou na rodada ${Math.max(1, round - 1)}`}</h3>
      <ol className="roundboard__list">{shown.map((e, i) => <Row key={i} e={e} />)}</ol>
      {compact && entries.length > RECENT && (
        <details className="roundboard__more">
          <summary>{`Ver a rodada inteira (${entries.length})`}</summary>
          <ol className="roundboard__list">{entries.map((e, i) => <Row key={i} e={e} />)}</ol>
        </details>
      )}
      <p className="sr-only" role="status" aria-live="polite">{`Rodada resolvida: ${entries.length} ${entries.length === 1 ? "jogada" : "jogadas"}.`}</p>
    </section>
  );
}
