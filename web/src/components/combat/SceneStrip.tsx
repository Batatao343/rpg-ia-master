import type { SceneCardsView, SceneObjectiveView, ScenePressagioView } from "../../types";
import { Icon } from "../../design/icons";
import { clockBody, clockLine, objectiveLine } from "../../combat/deck";

/** SPEC-334 R1 + SPEC-342 R2: faixa da cena. Sem `cena`/`objetivo`/`pressagios` (Cartas de Cena `off`) é só a rodada.
 *  Com eles: um `details` (1 elemento interativo) e, FORA dele, a previsão da próxima rodada. */
export function SceneStrip({ round, cena, objetivo, pressagios = [] }: {
  round: number;
  cena?: SceneCardsView;
  objetivo?: SceneObjectiveView;
  pressagios?: ScenePressagioView[];
}) {
  const omens = (
    <>
      {pressagios.map((p) => (
        <p key={p.id} className="scene-omen" data-scene-omen={p.id}>
          <Icon name={p.quando === "relogio" ? "abyss" : "warning"} />
          <span>Na próxima rodada: {p.pressagio}</span>
        </p>
      ))}
    </>
  );
  if (!cena && !objetivo) {
    return (
      <>
        <p className="scene-strip"><span>Rodada {round}</span></p>
        {omens}
      </>
    );
  }
  const goal = objetivo ? objectiveLine(objetivo) : "";
  return (
    <>
      <details className="scene-strip">
        <summary>
          <span>Rodada {round}</span>
          {cena?.cartas.map((c) => <span key={c.id} className="scene-strip__extra">{c.nome}</span>)}
          {goal && <span className="scene-strip__extra">{goal}</span>}
          {cena && <span className="scene-strip__extra scene-strip__clock">{clockLine(cena.relogio)}</span>}
        </summary>
        <div className="scene-strip__body">
          {cena?.cartas.map((c) => <p key={c.id}><strong>{c.nome}.</strong> {c.sabor}</p>)}
          {goal && <p>{goal}.</p>}
          {cena && <p>{clockBody(cena.relogio)}</p>}
        </div>
      </details>
      {omens}
    </>
  );
}
