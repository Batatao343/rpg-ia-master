import { useState } from "react";

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
  return !gameId || localStorage.getItem(LS_PREFIX + gameId) === "1";
}

export function OnboardingHint({ gameId }: { gameId: string }) {
  const [hidden, setHidden] = useState(false);
  if (hidden) return null;
  return (
    <aside className="onboard" aria-label="Como jogar">
      <div className="onboard__head">
        <p className="onboard__title">Você escreve, o mundo responde</p>
        <button
          className="iconbtn"
          type="button"
          aria-label="Dispensar dica"
          onClick={() => {
            localStorage.setItem(LS_PREFIX + gameId, "1");
            setHidden(true);
          }}
        >
          ✕
        </button>
      </div>
      <ul className="onboard__list">
        {EXAMPLES.map(([verb, ex]) => (
          <li key={verb}>
            <strong>{verb}</strong> — <em>“{ex}”</em>
          </li>
        ))}
      </ul>
      <p className="onboard__tip">
        Em combate, chips com suas habilidades aparecem acima da caixa de texto —
        um toque executa a ação.
      </p>
    </aside>
  );
}
