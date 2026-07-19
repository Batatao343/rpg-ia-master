import { useEffect, useState } from "react";
import type { GameResponse, LogEntry } from "../types";
import { StoryLog } from "./StoryLog";
import { Hud } from "./Hud";
import { LevelUpModal } from "./LevelUpModal";
import { OnboardingHint, onboardingDismissed } from "./OnboardingHint";

interface Props {
  data: GameResponse | null;
  log: LogEntry[];
  thinking: boolean;
  thinkingLabel?: string | null;
  busy: boolean;
  onAction: (text: string) => void;
  onNew: () => void;
  onLevelUp: (choiceId: string, pick: { ability_id?: string; attr?: string }) => void;
  onEquip: (pick: { item_id?: string; unequip_slot?: string }) => void;
}

export function PlayScreen({ data, log, thinking, thinkingLabel, busy, onAction, onNew, onLevelUp, onEquip }: Props) {
  const [input, setInput] = useState("");
  const [hudOpen, setHudOpen] = useState(false);
  const [luDismissed, setLuDismissed] = useState(false);
  const [reading, setReading] = useState(false); // memorial: ler a crônica

  const w = data?.world;
  // spec itens-vivos-e-luz: chip de luz no relógio (escuro sem fonte / iluminado).
  const lightChip = w?.light?.dark
    ? " · 🌑 Escuridão"
    : w?.light?.label === "iluminado pela sua luz"
    ? " · 🔦 Iluminado"
    : "";
  const clock = (w?.period ? `Dia ${w.day} · ${w.period}` : "Dia 1 · Amanhecer")
    + (w?.weather ? ` · ${w.weather}` : "")
    + lightChip;
  // spec mapa-sublocais: interiores do local atual + saída quando dentro de um
  const interiorsHere = w?.interiors?.here ?? [];
  const exitTo = w?.interiors?.exit_to ?? null;
  const dead = (data?.player_stats.hp ?? 1) <= 0;
  const fighting = !!data?.combat?.active;
  // spec polish-sessao (R4): chips 100% mecânicos — SÓ em combate
  const suggestions = fighting && !dead ? data?.combat?.suggestions ?? [] : [];
  // spec polish-sessao (R6): onboarding no 1º turno (dismissible por jogo)
  const showOnboard =
    !dead && (data?.world?.turn_count ?? 99) <= 1 && !onboardingDismissed(data?.game_id ?? null);

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

      {(interiorsHere.length > 0 || exitTo) && !fighting && !dead && (
        <div className="placesbar">
          {exitTo && (
            <button className="placechip placechip--exit" type="button" disabled={busy}
                    onClick={() => onAction(`Saio para ${exitTo.name}`)}>
              ↩ Sair para {exitTo.name}
            </button>
          )}
          {interiorsHere.map((i) => (
            <button key={i.id} className="placechip" type="button" disabled={busy}
                    onClick={() => onAction(`Entro em ${i.name}`)}>
              ⌂ {i.name}
            </button>
          ))}
        </div>
      )}

      <div className="stage">
        <StoryLog entries={log} thinking={thinking} thinkingLabel={thinkingLabel} />
        <Hud data={data} open={hudOpen} onEquip={onEquip} busy={busy} />
      </div>

      {showOnboard && data?.game_id && <OnboardingHint gameId={data.game_id} />}

      {suggestions.length > 0 && (
        <div className="actionchips" role="group" aria-label="Ações sugeridas">
          {suggestions.map((s) => (
            <button key={s} className="actionchip" type="button" disabled={busy}
                    onClick={() => onAction(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      <form className="actionbar" onSubmit={submit}>
        <input
          type="text"
          autoComplete="off"
          disabled={dead}
          placeholder={
            dead
              ? "Memorial — a crônica permanece."
              : fighting
                ? "O inimigo avança — o que você faz?"
                : "O que você faz?  (ex.: examino a porta, ataco o vulto, pergunto sobre o rei)"
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="btn btn--primary" type="submit" disabled={busy || dead} aria-label="Agir">
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

      {dead && !reading && (
        <div className="overlay">
          <div className="overlay__inner">
            <p className="overlay__big">VOCÊ MORREU</p>
            <p className="muted">O fio do destino se rompeu.</p>
            <button className="btn btn--primary" type="button" onClick={onNew}>
              Começar de novo
            </button>
            {/* spec polish-sessao (R3): memorial abre em modo leitura */}
            <button className="btn" type="button"
                    onClick={() => { setReading(true); setHudOpen(true); }}>
              Ler a crônica
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
