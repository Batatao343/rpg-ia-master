import { useState } from "react";
import { safeStorage } from "../safeStorage";
import { Icon } from "../design/icons";

// spec polish-sessao (R6): painel dismissible do 1º turno — ensina os comandos
// que o motor entende. 100% frontend; "dispensado" fica em localStorage por jogo.
const EXAMPLES = [
  ["viajar", "Viajo para o Pântano da Melancolia"],
  ["descansar", "Descanso junto à fogueira"],
  ["equipar", "Equipo o arco de caça"],
  ["falar", "Falo com o taverneiro sobre rumores"],
  ["atacar", "Ataco o vulto nas sombras"],
];

const LS_PREFIX = "cronicas_onboard_";

export function onboardingDismissed(gameId: string | null): boolean {
  return !gameId || safeStorage.get(LS_PREFIX + gameId) === "1";
}

export function OnboardingHint({ gameId, compact = false }: { gameId: string; compact?: boolean }) {
  const [hidden, setHidden] = useState(false);
  if (hidden) return null;
  const dismiss = (
    <button
      className="iconbtn"
      type="button"
      aria-label="Dispensar dica"
      onClick={() => {
        safeStorage.set(LS_PREFIX + gameId, "1");
        setHidden(true);
      }}
    >
      <Icon name="close" />
    </button>
  );
  const body = (
    <>
      <ul className="onboard__list">
        {EXAMPLES.map(([verb, ex]) => (
          <li key={verb}>
            <strong>{verb}</strong> — <em>“{ex}”</em>
          </li>
        ))}
      </ul>
      <p className="onboard__tip">
        Em combate, abra a aba Combate para jogar Cartas — ou descreva a ação.
        Cada turno leva uns 10 segundos: o narrador está pensando, não travou.
        Prefere falar? O botão Voz grava a ação para você.
      </p>
    </>
  );
  // SPEC-345 R10.2: no celular a dica nasce recolhida (não cobre a 1ª narração).
  if (compact) {
    return (
      <details className="onboard onboard--compact" aria-label="Como jogar">
        <summary className="onboard__head">
          <span className="onboard__title">Você escreve, o mundo responde</span>
        </summary>
        <div className="onboard__dismiss">{dismiss}</div>
        {body}
      </details>
    );
  }
  return (
    <aside className="onboard" aria-label="Como jogar">
      <div className="onboard__head">
        <p className="onboard__title">Você escreve, o mundo responde</p>
        {dismiss}
      </div>
      {body}
    </aside>
  );
}
