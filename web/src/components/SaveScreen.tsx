import { useState } from "react";
import type { SaveSummary } from "../types";
import { Frame, Divider, Medallion } from "./ornaments";

// spec polish-sessao (R3): tela "Continuar jornada" — lista campanhas salvas
// com Continuar / Excluir (confirmação com o nome do herói) / Nova jornada.
interface Props {
  saves: SaveSummary[];
  busy: boolean;
  onContinue: (gameId: string) => void;
  onDelete: (gameId: string) => void;
  onNew: () => void;
}

export function SaveScreen({ saves, busy, onContinue, onDelete, onNew }: Props) {
  const [confirming, setConfirming] = useState<SaveSummary | null>(null);

  return (
    <main className="create saves-screen">
      <Frame className="create__frame">
        <div className="create__seal"><Medallion size={48} /></div>
        <h1 className="create__title">Continuar jornada</h1>
        <Divider />
        <ul className="savelist">
          {saves.map((s) => (
            <li key={s.game_id} className={"savecard" + (s.game_over ? " is-memorial" : "")}>
              <button
                className="savecard__main"
                type="button"
                disabled={busy}
                onClick={() => onContinue(s.game_id)}
              >
                <span className="savecard__name">
                  {s.name}
                  {s.game_over && <span className="savecard__badge">⚰ memorial</span>}
                </span>
                <span className="savecard__meta">
                  {s.class_name} · nível {s.level}
                </span>
                <span className="savecard__meta">
                  {s.location} — dia {s.day}
                </span>
              </button>
              <button
                className="iconbtn savecard__del"
                type="button"
                disabled={busy}
                aria-label={"Excluir a jornada de " + s.name}
                onClick={() => setConfirming(s)}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
        <Divider />
        <button className="btn btn--primary" type="button" disabled={busy} onClick={onNew}>
          Nova jornada
        </button>
      </Frame>

      {confirming && (
        <div className="overlay">
          <div className="overlay__inner">
            <p className="overlay__big">Apagar esta saga?</p>
            <p className="muted">
              A jornada de <strong>{confirming.name}</strong> será perdida para sempre —
              crônica, feitos e memórias.
            </p>
            <div className="savecard__confirm">
              <button
                className="btn btn--danger"
                type="button"
                disabled={busy}
                onClick={() => {
                  onDelete(confirming.game_id);
                  setConfirming(null);
                }}
              >
                Apagar {confirming.name}
              </button>
              <button className="btn" type="button" onClick={() => setConfirming(null)}>
                Manter
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
