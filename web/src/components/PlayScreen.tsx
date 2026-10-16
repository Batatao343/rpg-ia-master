import { useEffect, useRef, useState } from "react";
import type { ActionOptions, GameResponse, LogEntry } from "../types";
import { LevelUpModal, type LevelUpPick } from "./LevelUpModal";
import { shards } from "./AccountScreen";
import { Workspace, type WorkspaceHandle } from "../workspace/Workspace";
import { useModalFocus } from "../workspace/useModalFocus";

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
  onAccount?: () => void;
  accountBalance?: string | null;
  /** Dono da sessão: escopo da preferência de layout (SPEC-204 R9). */
  owner?: string;
}

/** SPEC-204: orquestrador da tela de jogo — topbar + workspace (chat + UM painel)
 *  + overlays. Controles táticos vivem só na aba Combate do workspace. */
export function PlayScreen({ data, log, thinking, thinkingLabel, busy, onAction, onNew, onLevelUp, onEquip, onLogout, onAccount, accountBalance, owner = "legacy" }: Props) {
  const [luDismissed, setLuDismissed] = useState(false);
  const [reading, setReading] = useState(false); // memorial: ler a crônica
  const workspace = useRef<WorkspaceHandle>(null);

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
  const gameOver = !!data?.game_over;
  const deathPending = !!data?.death_pending;
  const simulation = !!data?.combat_simulation?.enabled;
  const simulationFinished = simulation && !!data?.combat_simulation?.finished;
  const blocked = gameOver || deathPending || simulationFinished;
  const fighting = !!data?.combat?.active;

  // Fase 4.1: escolha pendente reabre o modal quando MUDA (novo level up).
  const pending = data?.player_stats?.pending_choices ?? [];
  const pendingKey = pending[0]?.id ?? "";
  useEffect(() => setLuDismissed(false), [pendingKey]);
  const showLevelUp = pending.length > 0 && !luDismissed && !blocked && !fighting;

  return (
    <div className={"play" + (fighting ? " is-combat" : "")}>
      {fighting && <div className="combat-veil" aria-hidden />}

      <header className="topbar">
        <div className="topbar__loc">
          <span className="topbar__place">{data?.current_location || "—"}</span>
          <span className="topbar__meta">{clock}</span>
        </div>
        <div className="topbar__right">
          {onAccount && <button className="iconbtn" type="button" disabled={busy} onClick={onAccount}>
            Conta{accountBalance != null ? ` · ${shards(accountBalance)} Estilhas` : ""}
          </button>}
          {simulation && <span className="laboratory-flag">Laboratório</span>}
          {fighting && <span className="combat-flag">⚔ Combate</span>}
          {/* Fica montado com o modal aberto: o foco volta a ele ao fechar (R16). */}
          {pending.length > 0 && !blocked && (
            <button className="iconbtn iconbtn--levelup" type="button"
                    onClick={() => setLuDismissed(false)}>
              ⬆ Nível!
            </button>
          )}
          {/* Atalho para Personagem (SPEC-204): não fecha nem desloca o chat. */}
          <button className="iconbtn" type="button" onClick={() => workspace.current?.openTab("personagem")}>
            ☰ Ficha
          </button>
          <button className="iconbtn" type="button" disabled={busy} onClick={onNew}>
            {simulation ? "Reiniciar" : "Nova"}
          </button>
          {onLogout && <button className="iconbtn" type="button" disabled={busy}
            onClick={onLogout} aria-label="Encerrar sessão">Sair</button>}
        </div>
      </header>

      <Workspace key={data?.game_id ?? "sem-jogo"} ref={workspace} owner={owner} data={data} log={log}
        thinking={thinking} thinkingLabel={thinkingLabel} busy={busy} blocked={blocked}
        onAction={onAction} onEquip={onEquip} />

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
        <ModalOverlay className="overlay simulation-result" labelledBy="simulation-result-title">
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
        </ModalOverlay>
      )}

      {gameOver && !reading && !simulation && (
        <ModalOverlay className="overlay" labelledBy="game-over-title">
          <div className="overlay__inner">
            <p id="game-over-title" className="overlay__big">VOCÊ MORREU</p>
            <p className="muted">O fio do destino se rompeu.</p>
            <button className="btn btn--primary" type="button" onClick={onNew}>
              Começar de novo
            </button>
            {/* spec polish-sessao (R3): memorial abre em modo leitura — Codex › Crônica */}
            <button className="btn" type="button"
                    onClick={() => { setReading(true); workspace.current?.openTab("codex", { codexSection: "cronica" }); }}>
              Ler a crônica
            </button>
          </div>
        </ModalOverlay>
      )}
    </div>
  );
}

/** Overlay modal de viewport inteiro com foco preso e devolvido (SPEC-204 R16). */
function ModalOverlay({ className, labelledBy, children }: { className: string; labelledBy: string; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useModalFocus(ref);
  return (
    <div ref={ref} className={className} role="dialog" aria-modal="true" aria-labelledby={labelledBy} tabIndex={-1}>
      {children}
    </div>
  );
}
