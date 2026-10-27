import type { PilesView } from "../../types";
import type { FolegoState } from "../../combat/deck";

/** SPEC-334 R3 + SPEC-342 R9.4/R20: Fôlego em texto ("Fôlego 2 de 3", fonte acessível) + pips só visuais.
 *  Livre = disco cheio; reservado pela fila = anel cheio de contorno; vazio = anel tracejado. O Pacto do Abismo
 *  (emprestado) usa a cor de Entropia; o `status` fica sempre montado para o aviso ser anunciado ao aparecer. */
export function FolegoPips({ piles, state }: { piles: PilesView; state: FolegoState }) {
  const own = Math.max(0, piles.folego);
  return (
    <span className="folego">
      <span className="folego__label">Fôlego {state.free} de {piles.folego_max}</span>
      <span className="folego__pips" aria-hidden="true">
        {Array.from({ length: Math.max(piles.folego_max, own) }, (_, i) => (
          <span key={i} className={`folego__pip${i < own ? "" : " is-empty"}${i < own && i >= state.free ? " is-reserved" : ""}`} />
        ))}
        {Array.from({ length: piles.pacto_max }, (_, i) => (
          <span key={`p${i}`} className={`folego__pip folego__pip--pacto${i < state.borrowed ? " is-reserved" : ""}`} />
        ))}
      </span>
      <span className="folego__warn" role="status">
        {state.borrowed > 0 ? `O Abismo empresta ${state.borrowed} de fôlego: custa Entropia e +1 Carga.` : ""}
      </span>
    </span>
  );
}
