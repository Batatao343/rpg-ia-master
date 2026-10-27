import type { PilesView } from "../../types";
import type { FolegoState } from "../../combat/deck";

/** SPEC-334 R3: 3 pips de Fôlego (cheio = livre, riscado = reservado pela fila) e, ao fim, os pips do
 *  Pacto do Abismo "emprestados" em cor de Entropia — com o aviso do custo quando a fila os usa. */
export function FolegoPips({ piles, state }: { piles: PilesView; state: FolegoState }) {
  const own = Math.max(0, piles.folego);
  const label = `Fôlego: ${state.free} livre${state.free === 1 ? "" : "s"} de ${piles.folego_max}` +
    (state.borrowed ? `; a fila toma ${state.borrowed} emprestado do Abismo` : "");
  return (
    <div className="folego" role="img" aria-label={label}>
      <span className="folego__pips" aria-hidden="true">
        {Array.from({ length: Math.max(piles.folego_max, own) }, (_, i) => (
          <span key={i} className={`folego__pip${i < own ? "" : " is-empty"}${i < own && i >= state.free ? " is-reserved" : ""}`} />
        ))}
        {Array.from({ length: piles.pacto_max }, (_, i) => (
          <span key={`p${i}`} className={`folego__pip folego__pip--pacto${i < state.borrowed ? " is-reserved" : ""}`} />
        ))}
      </span>
      <span className="folego__label">Fôlego</span>
      {state.borrowed > 0 && (
        <span className="folego__warn" role="status">
          Pacto do Abismo: {state.borrowed} emprestado — custa Entropia e +1 Carga.
        </span>
      )}
    </div>
  );
}
