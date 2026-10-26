import { useRef, useState, type ReactNode } from "react";
import type { ActionOptions, GameResponse, LogEntry } from "../types";
import type { TurnWait } from "../turnWait";
import { LevelUpModal, type LevelUpPick } from "./LevelUpModal";
import { shards } from "./AccountScreen";
import { Workspace, type WorkspaceHandle } from "../workspace/Workspace";
import { useModalFocus } from "../workspace/useModalFocus";
import { levelUpHeldByOutcome, resultFrom } from "../combatOutcome";
import { clockLabel } from "../clockLabel";
import { useIsCompact } from "../hooks/useIsCompact";
import { ConfirmNewDialog, PlayMenu } from "./PlayMenu";

interface Props {
  data: GameResponse | null;
  log: LogEntry[];
  thinking: boolean;
  /** SPEC-320: espera do turno + retry; banner entra no fluxo abaixo da topbar. */
  turn?: TurnWait;
  onRetryTurn?: () => void;
  banner?: ReactNode;
  busy: boolean;
  onAction: (text: string, options?: ActionOptions) => void;
  onNew: () => void;
  onLevelUp: (choiceId: string, pick: LevelUpPick) => void;
  onEquip: (pick: { item_id?: string; unequip_slot?: string }) => void;
  onPrepareCards?: (prepared: string[]) => Promise<string | null>;
  onLogout?: () => void;
  onAccount?: () => void;
  accountBalance?: string | null;
  /** SPEC-321 R3: há ação pendente / turno não registrado — "Nova jornada" pede confirmação. */
  confirmLeave?: boolean;
  /** SPEC-321 R6: ofertas de arte (retrato no painel Personagem; cena/NPC como chip na narração). */
  artPanel?: ReactNode;
  onQuoteOffer?: (offer: NonNullable<GameResponse["art_offers"]>[number]) => void;
  offersDisabled?: boolean;
  /** Dono da sessão: escopo da preferência de layout (SPEC-204 R9). */
  owner?: string;
}

/** SPEC-204: orquestrador da tela de jogo — topbar + workspace (chat + UM painel)
 *  + overlays. Controles táticos vivem só na aba Combate do workspace. */
export function PlayScreen({ data, log, thinking, turn, onRetryTurn, banner, busy, onAction, onNew, onLevelUp, onEquip, onPrepareCards, onLogout, onAccount, accountBalance, confirmLeave = false, artPanel, onQuoteOffer, offersDisabled, owner = "legacy" }: Props) {
  const compact = useIsCompact();
  const [confirmingNew, setConfirmingNew] = useState(false);
  const [luDismissedKey, setLuDismissedKey] = useState<string | null>(null);
  const [dismissedResult, setDismissedResult] = useState<string | null>(null);
  const [reading, setReading] = useState(false); // memorial: ler a crônica
  const workspace = useRef<WorkspaceHandle>(null);

  const w = data?.world;
  // spec itens-vivos-e-luz: chip de luz no relógio (escuro sem fonte / iluminado).
  const lightChip = w?.light?.dark
    ? " · 🌑 Escuridão"
    : w?.light?.label === "iluminado pela sua luz"
    ? " · 🔦 Iluminado"
    : "";
  const clock = clockLabel(w)
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
  const luDismissed = luDismissedKey === pendingKey;
  // SPEC-212: o desfecho do combate vem primeiro; o modal de nível abre após "Continuar".
  const outcomeFirst = levelUpHeldByOutcome(resultFrom(data?.combat_result), dismissedResult);
  // Pedido explícito (chip/aba): abre o modal já, dispensando o painel de desfecho.
  const openLevelUp = () => {
    const res = resultFrom(data?.combat_result);
    if (res) setDismissedResult(res.result_event_id);
    setLuDismissedKey(null);
  };
  const requestNew = () => { if (confirmLeave) setConfirmingNew(true); else onNew(); };
  const levelUpChip = pending.length > 0 && !blocked && (
    <button className="iconbtn iconbtn--levelup" type="button" onClick={openLevelUp}>
      ⬆ Nível!
    </button>
  );
  const showLevelUp = pending.length > 0 && !luDismissed && !blocked && !fighting && !outcomeFirst;

  return (
    <div className={"play" + (fighting ? " is-combat" : "")}>
      {fighting && <div className="combat-veil" aria-hidden />}

      {!compact && (
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
            {levelUpChip}
            {/* Atalho para Personagem (SPEC-204): não fecha nem desloca o chat. */}
            <button className="iconbtn" type="button" onClick={() => workspace.current?.openTab("personagem")}>
              ☰ Ficha
            </button>
            <button className="iconbtn topbar__new" type="button" disabled={busy} onClick={requestNew}>
              {simulation ? "Reiniciar" : "Nova jornada"}
            </button>
            {onLogout && <button className="iconbtn" type="button" disabled={busy}
              onClick={onLogout} aria-label="Encerrar sessão">Sair</button>}
          </div>
        </header>
      )}
      {!compact && banner}

      <Workspace key={data?.game_id ?? "sem-jogo"} ref={workspace} owner={owner} data={data} log={log}
        thinking={thinking} turn={turn} onRetryTurn={onRetryTurn} busy={busy} blocked={blocked}
        onAction={onAction} onEquip={onEquip}
        onPrepareCards={onPrepareCards} onOpenLevelUp={openLevelUp}
        artPanel={artPanel} onQuoteOffer={onQuoteOffer} offersDisabled={offersDisabled}
        place={data?.current_location || "—"} banner={compact ? banner : undefined}
        headActions={compact ? (
          <>
            {levelUpChip}
            <PlayMenu busy={busy} simulation={simulation} accountBalance={accountBalance}
              onAccount={onAccount} onNew={requestNew} onLogout={onLogout} />
          </>
        ) : undefined}
        dismissedResult={dismissedResult} onDismissResult={setDismissedResult} />

      {showLevelUp && data && (
        <LevelUpModal
          key={pendingKey}
          player={data.player_stats}
          busy={busy}
          onChoose={onLevelUp}
          onLater={() => setLuDismissedKey(pendingKey)}
        />
      )}

      {confirmingNew && (
        <ConfirmNewDialog simulation={simulation} onCancel={() => setConfirmingNew(false)}
          onConfirm={() => { setConfirmingNew(false); onNew(); }} />
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
