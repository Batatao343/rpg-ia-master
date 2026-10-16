import { forwardRef, useCallback, useState } from "react";
import type { ActionOptions, GameResponse, LogEntry, TurnOutcome } from "../types";
import { StoryLog } from "../components/StoryLog";
import { SceneArtwork } from "../components/SceneArtwork";
import { OutcomeToast } from "../components/OutcomeToast";
import { CombatOutcomePanel } from "../components/CombatOutcomePanel";
import { resultFrom, shouldShowResult } from "../combatOutcome";
import { OnboardingHint, onboardingDismissed } from "../components/OnboardingHint";
import { useVoiceInput } from "../voice/useVoiceInput";
import { getChatSession, setChatSession } from "./chatSessionStore";

/** SPEC-204: superfície do chat — arte de cena, atalhos de lugar e a narrativa. */
export function ChatSurface({ data, log, thinking, thinkingLabel, busy, blocked, active, onAction }: {
  data: GameResponse | null;
  log: LogEntry[];
  thinking: boolean;
  thinkingLabel?: string | null;
  busy: boolean;
  blocked: boolean;
  active: boolean;
  onAction: (text: string, options?: ActionOptions) => void;
}) {
  const gameId = data?.game_id;
  const fighting = !!data?.combat?.active;
  const simulation = !!data?.combat_simulation?.enabled;
  const interiorsHere = data?.world?.interiors?.here ?? [];
  const exitTo = data?.world?.interiors?.exit_to ?? null;
  const showOnboard = !simulation && !blocked && (data?.world?.turn_count ?? 99) <= 1
    && !onboardingDismissed(gameId ?? null);
  const [initialScroll] = useState(() => getChatSession(gameId));
  // SPEC-203 R8: "Continuar" fecha só o painel (estado local; reload o reexibe).
  const [dismissedResult, setDismissedResult] = useState<string | null>(null);
  const combatResult = resultFrom(data?.combat_result);
  const onScrollPosition = useCallback((scrollTop: number, atBottom: boolean) =>
    setChatSession(gameId, { scrollTop, atBottom }), [gameId]);

  return (
    <section className="ws-chat" aria-label="Chat da aventura" hidden={!active}>
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
      <div className="narrative-stage">
        <SceneArtwork scene={data?.visual?.scene} />
        {/* SPEC-199: chip mecânico do turno (aria-live, sem role="status"). */}
        <OutcomeToast outcome={data?.turn_outcome?.receipt_id ? (data.turn_outcome as TurnOutcome) : null} />
        {combatResult && shouldShowResult(combatResult, dismissedResult) && (
          <CombatOutcomePanel result={combatResult} outcome={data?.turn_outcome}
            onContinue={() => setDismissedResult(combatResult.result_event_id)} />
        )}
        {showOnboard && gameId && <OnboardingHint gameId={gameId} />}
        <StoryLog entries={log} thinking={thinking} thinkingLabel={thinkingLabel} active={active}
          initialScroll={initialScroll}
          onScrollPosition={onScrollPosition} />
      </div>
    </section>
  );
}

/** Composer: sempre visível em todos os modos (R6: Esc no contexto devolve o foco aqui).
 *  O rascunho vive em memória por game_id (R7/R8, §8 P3 — nunca em disco). */
export const Composer = forwardRef<HTMLInputElement, {
  data: GameResponse | null;
  busy: boolean;
  blocked: boolean;
  reactionCardId?: string;
  onAction: (text: string, options?: ActionOptions) => void;
}>(function Composer({ data, busy, blocked, reactionCardId, onAction }, inputRef) {
  const gameId = data?.game_id;
  const [input, setInputState] = useState(() => getChatSession(gameId).draft);
  const setInput = (update: string | ((current: string) => string)) => {
    setInputState((current) => {
      const next = typeof update === "function" ? update(current) : update;
      setChatSession(gameId, { draft: next });
      return next;
    });
  };
  const voice = useVoiceInput(text => setInput(current => current ? `${current}${/\s$/.test(current) ? "" : " "}${text}` : text), gameId);
  const voiceActive = voice.requesting || ["recording", "uploading", "transcribing"].includes(voice.phase);
  const gameOver = !!data?.game_over;
  const deathPending = !!data?.death_pending;
  const simulation = !!data?.combat_simulation?.enabled;
  const simulationFinished = simulation && !!data?.combat_simulation?.finished;
  const fighting = !!data?.combat?.active;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || blocked) return;
    const text = input.trim();
    if (!text) return;
    // Explicit text submission cancels any outstanding capture/transcript.
    if (voiceActive) voice.cancel();
    setInput("");
    onAction(text, { reaction_card_id: reactionCardId });
  }

  return (
    <form className="actionbar ws-composer" onSubmit={submit}>
      <div className="actionbar__composer">
      <input
        ref={inputRef}
        type="text"
        aria-label="Sua ação"
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
      <button className="btn voice-button" type="button"
        disabled={blocked || (voice.phase !== "recording" && (busy || voiceActive))}
        aria-label={voice.phase === "recording" ? "Parar gravação" : "Gravar ação por voz"}
        aria-pressed={voice.phase === "recording"}
        onClick={voice.phase === "recording" ? voice.stop : voice.start}>
        {voice.phase === "recording" ? "Parar" : "Voz"}
      </button>
      {/* SPEC-201 A13: estado pendente com texto e aria-busy, não só "…". */}
      <button className="btn btn--primary" type="submit" disabled={busy || blocked} aria-label="Agir" aria-busy={busy}>
        {busy ? "Enviando…" : fighting ? "Lutar" : "Agir"}
      </button>
      </div>
      <div className="voice-status" data-voice-state={voice.phase}>
        <span role={voice.phase === "error" ? "alert" : "status"} aria-live="polite" aria-atomic="true">
          {voice.message}
        </span>
        {voice.phase === "recording" && <span className="voice-timer" aria-label="Tempo de gravação">
          {String(voice.seconds).padStart(2, "0")} / 60 s
        </span>}
        {voiceActive && <button type="button" className="iconbtn" onClick={voice.cancel}>
          Cancelar voz
        </button>}
      </div>
    </form>
  );
});
