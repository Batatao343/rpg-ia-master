import type { PressagioView } from "../../types";
import { pressagioLine } from "../../combat/deck";

/** SPEC-334 R1: presságio de cada inimigo (sinal do catálogo + faixa/valor conforme o conhecimento,
 *  SPEC-329 R3). Nome e Vitalidade já vivem na Arena; aqui só o que o inimigo vai fazer. */
export function EnemyStrip({ pressagios, nameOf }: { pressagios: PressagioView[]; nameOf: (id: string) => string | undefined }) {
  if (!pressagios.length) return null;
  return (
    <ul className="enemy-strip" aria-label="Presságios dos inimigos">
      {pressagios.map((p, i) => (
        <li key={`${p.actor_id}-${i}`} data-pressagio={p.tipo}>{pressagioLine(p, nameOf)}</li>
      ))}
    </ul>
  );
}
