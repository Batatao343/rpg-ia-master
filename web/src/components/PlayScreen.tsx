import { useState } from "react";
import type { GameResponse, LogEntry } from "../types";
import { StoryLog } from "./StoryLog";
import { Hud } from "./Hud";

interface Props {
  data: GameResponse | null;
  log: LogEntry[];
  thinking: boolean;
  busy: boolean;
  onAction: (text: string) => void;
  onNew: () => void;
}

export function PlayScreen({ data, log, thinking, busy, onAction, onNew }: Props) {
  const [input, setInput] = useState("");
  const [hudOpen, setHudOpen] = useState(false);

  const w = data?.world;
  const clock = w?.period ? `Dia ${w.day} · ${w.period}` : "Dia 1 · Amanhecer";
  const dead = (data?.player_stats.hp ?? 1) <= 0;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");
    onAction(text);
  }

  return (
    <div className="play">
      <header className="topbar">
        <div className="topbar__loc">
          <span className="topbar__place">{data?.current_location || "—"}</span>
          <span className="topbar__meta">{clock}</span>
        </div>
        <div className="topbar__right">
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
        <Hud data={data} open={hudOpen} />
      </div>

      <form className="actionbar" onSubmit={submit}>
        <input
          type="text"
          autoComplete="off"
          placeholder="O que você faz?  (ex.: examino a porta, ataco o vulto, pergunto sobre o rei)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="btn btn--primary" type="submit" disabled={busy} aria-label="Agir">
          {busy ? "…" : "Agir"}
        </button>
      </form>

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
