/** SPEC-334 R1: faixa única da cena — contador de rodadas. As Cartas de Cena e o Relógio do Abismo
 *  (SPEC-331) entram em `extras` quando a API os mandar; sem eles, só a rodada. */
export function SceneStrip({ round, extras = [] }: { round: number; extras?: Array<{ key: string; label: string }> }) {
  return (
    <p className="scene-strip">
      <span>Rodada {round}</span>
      {extras.map((e) => <span key={e.key} className="scene-strip__extra">{e.label}</span>)}
    </p>
  );
}
