import type { RoundLogEntry } from "../../types";
import { effectLine, roundEntryKind, roundLogView } from "../../combat/deck";
import { displayName } from "../../combat/displayName";
import { Icon } from "../../design/icons";

const RECENT = 4;
const EFFECTS_SHOWN = 2;

function Row({ e }: { e: RoundLogEntry }) {
  const v = roundLogView(e);
  const who = e.ator_id === "player" ? "Você" : displayName(v.who, e.ator_id);
  return (
    <li className={`roundboard__row roundboard__row--${e.lado}`} data-origem={e.origem}>
      <span className="roundboard__who">{e.lado === "heroi" ? <Icon name="combat" /> : null}<strong>{who}</strong></span>
      <span className="roundboard__card" data-reacao={e.origem === "reacao" ? "" : undefined}>{v.card}</span>
      {v.to && <><span className="roundboard__arrow" aria-hidden="true">→</span><span className="roundboard__to">{displayName(v.to, e.alvo_id ?? "")}</span></>}
      <span className={`roundboard__chip roundboard__chip--${v.tone}`}>{v.chip}</span>
    </li>
  );
}

/** SPEC-354 R5.3: efeito (dano contínuo, queda, presságio cumprido) — sem ícone de herói nem "Você" como autor. */
function EffectRow({ e }: { e: RoundLogEntry }) {
  const who = displayName(e.ator_nome, e.ator_id);
  return (
    <li className={`roundboard__row roundboard__row--efeito roundboard__row--${e.lado}`} data-efeito={roundEntryKind(e)}>
      <span className="roundboard__fx">{effectLine(e, who, e.ator_id === "player")}</span>
    </li>
  );
}

/** SPEC-347 R14.3 / SPEC-354: o registro das cartas da última rodada resolvida, entre a faixa de cena e a Arena.
 *  Uma coluna; "Jogadas" mostra as 4 últimas (em qualquer largura) e "Efeitos da rodada" vem à parte.
 *  Sem entradas não renderiza nada. `compact` só é mantido por compatibilidade (a regra agora é a mesma). */
export function RoundBoard({ entries, round, title }: { entries: RoundLogEntry[] | undefined; round: number; compact?: boolean; title?: string }) {
  if (!entries || entries.length === 0) return null;
  const plays = entries.filter((e) => roundEntryKind(e) === "jogada");
  const effects = entries.filter((e) => roundEntryKind(e) !== "jogada");
  const heading = title ?? `O que se jogou na rodada ${Math.max(1, round - 1)}`;
  const hidden = plays.length > RECENT || effects.length > EFFECTS_SHOWN;
  return (
    <section className="roundboard" aria-label={heading} data-roundboard>
      <h3 className="roundboard__title section-label">{heading}</h3>
      <ol className="roundboard__list">{plays.slice(-RECENT).map((e, i) => <Row key={i} e={e} />)}</ol>
      {effects.length > 0 && (
        <>
          <h4 className="roundboard__subtitle section-label">Efeitos da rodada</h4>
          <ol className="roundboard__list roundboard__list--efeitos">{effects.slice(0, EFFECTS_SHOWN).map((e, i) => <EffectRow key={i} e={e} />)}</ol>
        </>
      )}
      {hidden && (
        <details className="roundboard__more">
          <summary>{`Ver a rodada inteira (${entries.length})`}</summary>
          <ol className="roundboard__list">{plays.map((e, i) => <Row key={i} e={e} />)}</ol>
          {effects.length > 0 && <ol className="roundboard__list roundboard__list--efeitos">{effects.map((e, i) => <EffectRow key={i} e={e} />)}</ol>}
        </details>
      )}
      <p className="sr-only" role="status" aria-live="polite">{`Rodada resolvida: ${entries.length} ${entries.length === 1 ? "jogada" : "jogadas"}.`}</p>
    </section>
  );
}
