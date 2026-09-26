import { useEffect, useState } from "react";
import type { ActionOptions, GameResponse, LogEntry } from "../types";
import { StoryLog } from "./StoryLog";
import { Hud } from "./Hud";
import { LevelUpModal, type LevelUpPick } from "./LevelUpModal";
import { OnboardingHint, onboardingDismissed } from "./OnboardingHint";
import { CardHand } from "./CardHand";
import { ReactionPrompt } from "./ReactionPrompt";
import { SceneZones } from "./SceneZones";
import { WoundTrack } from "./WoundTrack";
import { SceneArtwork } from "./SceneArtwork";

const TACTICAL_MANEUVERS = [
  { label: "Engajar", kind: "maneuver" as const, maneuver: "engajar" as const },
  { label: "Guardar", kind: "maneuver" as const, maneuver: "guardar" as const },
  { label: "Esconder-se", kind: "maneuver" as const, maneuver: "esconder" as const },
  { label: "Procurar", kind: "maneuver" as const, maneuver: "procurar" as const },
  { label: "Fugir", kind: "flee" as const },
];

interface Props {
  data: GameResponse | null;
  log: LogEntry[];
  thinking: boolean;
  thinkingLabel?: string | null;
  busy: boolean;
  onAction: (text: string, options?: ActionOptions) => void;
  onNew: () => void;
  onLevelUp: (choiceId: string, pick: LevelUpPick) => void;
  onEquip: (pick: { item_id?: string; unequip_slot?: string }) => void;
  onLogout?: () => void;
}

export function PlayScreen({ data, log, thinking, thinkingLabel, busy, onAction, onNew, onLevelUp, onEquip, onLogout }: Props) {
  const [input, setInput] = useState("");
  const [hudOpen, setHudOpen] = useState(false);
  const [luDismissed, setLuDismissed] = useState(false);
  const [reading, setReading] = useState(false); // memorial: ler a crônica
  const [reactionCardId, setReactionCardId] = useState<string | undefined>();

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
  const gameOver = !!data?.game_over;
  const deathPending = !!data?.death_pending;
  const simulation = !!data?.combat_simulation?.enabled;
  const simulationFinished = simulation && !!data?.combat_simulation?.finished;
  const blocked = gameOver || deathPending || simulationFinished;
  const fighting = !!data?.combat?.active;
  const combat = data?.combat;
  const maneuvers = fighting && !blocked
    ? (simulation
      ? [{ label: "Ataque básico", kind: "attack" as const }, ...TACTICAL_MANEUVERS]
      : TACTICAL_MANEUVERS)
    : [];
  // spec polish-sessao (R6): onboarding no 1º turno (dismissible por jogo)
  const showOnboard =
    !simulation && !blocked && (data?.world?.turn_count ?? 99) <= 1
    && !onboardingDismissed(data?.game_id ?? null);

  // Fase 4.1: escolha pendente reabre o modal quando MUDA (novo level up).
  const pending = data?.player_stats?.pending_choices ?? [];
  const pendingKey = pending[0]?.id ?? "";
  useEffect(() => setLuDismissed(false), [pendingKey]);
  useEffect(() => {
    const selected = combat?.cards?.find((card) => card.id === reactionCardId);
    if (reactionCardId && (!selected || !selected.ready)) setReactionCardId(undefined);
  }, [combat?.cards, reactionCardId]);
  const showLevelUp = pending.length > 0 && !luDismissed && !blocked && !fighting;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    setInput("");
    onAction(text, { reaction_card_id: reactionCardId });
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
          {simulation && <span className="laboratory-flag">Laboratório</span>}
          {fighting && <span className="combat-flag">⚔ Combate</span>}
          {pending.length > 0 && !showLevelUp && !blocked && (
            <button className="iconbtn iconbtn--levelup" type="button"
                    onClick={() => setLuDismissed(false)}>
              ⬆ Nível!
            </button>
          )}
          <button className="iconbtn" type="button" onClick={() => setHudOpen((v) => !v)}>
            ☰ Ficha
          </button>
          <button className="iconbtn" type="button" disabled={busy} onClick={onNew}>
            {simulation ? "Reiniciar" : "Nova"}
          </button>
          {onLogout && <button className="iconbtn" type="button" disabled={busy}
            onClick={onLogout} aria-label="Encerrar sessão">Sair</button>}
        </div>
      </header>

      {(interiorsHere.length > 0 || exitTo) && !fighting && !blocked && (
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
        <div className="narrative-stage">
          <SceneArtwork scene={data?.visual?.scene} />
          <StoryLog entries={log} thinking={thinking} thinkingLabel={thinkingLabel} />
        </div>
        <Hud data={data} open={hudOpen} onEquip={onEquip} busy={busy} />
      </div>

      {showOnboard && data?.game_id && <OnboardingHint gameId={data.game_id} />}

      {fighting && combat && !blocked && (
        <div className="tactical-dock">
          <CardHand
            cards={combat.cards}
            enemies={combat.enemies}
            busy={busy}
            reactionCardId={reactionCardId}
            onPlay={onAction}
          />
          <ReactionPrompt
            cards={combat.cards}
            selected={reactionCardId}
            disabled={busy}
            onSelect={setReactionCardId}
          />
          <div className="tactical-dock__status">
            <WoundTrack wounds={combat.wounds} compact />
            <SceneZones scene={combat.scene} chase={combat.chase} />
          </div>
        </div>
      )}

      {maneuvers.length > 0 && (
        <div className="actionchips" role="group" aria-label="Manobras táticas">
          {maneuvers.map((maneuver) => (
            <button key={maneuver.label} className="actionchip" type="button" disabled={busy}
                    onClick={() => onAction(maneuver.label, {
                      action_kind: maneuver.kind,
                      maneuver: "maneuver" in maneuver ? maneuver.maneuver : undefined,
                      reaction_card_id: reactionCardId,
                    })}>
              {maneuver.label}
            </button>
          ))}
        </div>
      )}

      <form className="actionbar" onSubmit={submit}>
        <input
          type="text"
          autoComplete="off"
          disabled={blocked}
          placeholder={
            gameOver
              ? "Memorial — a crônica permanece."
              : simulationFinished
                ? "Simulação encerrada."
              : deathPending
                ? "A Roda do Abismo aguarda sua escolha."
              : fighting
                ? simulation
                  ? "Texto livre executa um ataque básico; use os controles para ações precisas."
                  : "O inimigo avança — o que você faz?"
                : "O que você faz?  (ex.: examino a porta, ataco o vulto, pergunto sobre o rei)"
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="btn btn--primary" type="submit" disabled={busy || blocked} aria-label="Agir">
          {busy ? "…" : fighting ? "Lutar" : "Agir"}
        </button>
      </form>

      {showLevelUp && data && (
        <LevelUpModal
          key={pendingKey}
          player={data.player_stats}
          busy={busy}
          onChoose={onLevelUp}
          onLater={() => setLuDismissed(true)}
        />
      )}

      {simulationFinished && (
        <div className="overlay simulation-result" role="dialog" aria-modal="true" aria-labelledby="simulation-result-title">
          <div className="overlay__inner">
            <p className="kicker">Laboratório encerrado</p>
            <p id="simulation-result-title" className="overlay__big">
              {data?.combat_simulation?.outcome === "defeat" ? "DERROTA" : "VITÓRIA"}
            </p>
            <p className="muted">
              O resultado ficou isolado: sem XP, loot, memória ou avanço de campanha.
            </p>
            <button className="btn btn--primary" type="button" onClick={onNew}>
              Configurar nova simulação
            </button>
          </div>
        </div>
      )}

      {gameOver && !reading && !simulation && (
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
