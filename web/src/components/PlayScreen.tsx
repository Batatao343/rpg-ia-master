import { useEffect, useState } from "react";
import type { GameResponse, LogEntry } from "../types";
import { StoryLog } from "./StoryLog";
import { Hud } from "./Hud";
import { LevelUpModal } from "./LevelUpModal";

interface Props {
  data: GameResponse | null;
  log: LogEntry[];
  thinking: boolean;
  busy: boolean;
  onAction: (text: string) => void;
  onNew: () => void;
  onLevelUp: (choiceId: string, pick: { ability_id?: string; attr?: string }) => void;
  onEquip: (pick: { item_id?: string; unequip_slot?: string }) => void;
}

export function PlayScreen({ data, log, thinking, busy, onAction, onNew, onLevelUp, onEquip }: Props) {
  const [input, setInput] = useState("");
  const [hudOpen, setHudOpen] = useState(false);
  const [luDismissed, setLuDismissed] = useState(false);

  const w = data?.world;
  const clock = (w?.period ? `Dia ${w.day} · ${w.period}` : "Dia 1 · Amanhecer")
    + (w?.weather ? ` · ${w.weather}` : "");
  const dead = (data?.player_stats.hp ?? 1) <= 0;
  const fighting = !!data?.combat?.active;

  // Fase 4.1: escolha pendente reabre o modal quando MUDA (novo level up).
  const pending = data?.player_stats?.pending_choices ?? [];
  const pendingKey = pending[0]?.id ?? "";
  useEffect(() => setLuDismissed(false), [pendingKey]);
  const showLevelUp = pending.length > 0 && !luDismissed && !dead && !fighting;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");
    onAction(text);
  }

  return (
    <div className={"play" + (fighting ? " is-combat" : "")}>
      {fighting && <div className="combat-veil" aria-hidden />}

      <header className="topbar">
        <div className="topbar__loc">
          <span className="topbar__place">{data?.current_location || "—"}</span>
          <span className="topbar__meta">{clock}</span>
        </div>
        <div className="topbar__right">
          {fighting && <span className="combat-flag">⚔ Combate</span>}
          {pending.length > 0 && !showLevelUp && !dead && (
            <button className="iconbtn iconbtn--levelup" type="button"
                    onClick={() => setLuDismissed(false)}>
              ⬆ Nível!
            </button>
          )}
          <button className="iconbtn" type="button" onClick={() => setHudOpen((v) => !v)}>
            ☰ Ficha
          </button>
          <button className="iconbtn" type="button" onClick={onNew}>
            Nova
          </button>
        </div>
      </header>

      <div className="stage">
        <StoryLog entries={log} thinking={thinking} />
        <Hud data={data} open={hudOpen} onEquip={onEquip} busy={busy} />
      </div>

      <form className="actionbar" onSubmit={submit}>
        <input
          type="text"
          autoComplete="off"
          placeholder={
            fighting
              ? "O inimigo avança — o que você faz?"
              : "O que você faz?  (ex.: examino a porta, ataco o vulto, pergunto sobre o rei)"
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="btn btn--primary" type="submit" disabled={busy} aria-label="Agir">
          {busy ? "…" : fighting ? "Lutar" : "Agir"}
        </button>
      </form>

      {showLevelUp && data && (
        <LevelUpModal
          player={data.player_stats}
          busy={busy}
          onChoose={onLevelUp}
          onLater={() => setLuDismissed(true)}
        />
      )}

      {dead && (
        <div className="overlay">
          <div className="overlay__inner">
            <p className="overlay__big">VOCÊ MORREU</p>
            <p className="muted">O fio do destino se rompeu.</p>
            <button className="btn btn--primary" type="button" onClick={onNew}>
              Começar de novo
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
