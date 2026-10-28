import { forwardRef, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ActionOptions, GameResponse, LogEntry, TurnOutcome } from "../types";
import { StoryLog } from "../components/StoryLog";
import { SceneArtwork } from "../components/SceneArtwork";
import { OutcomeToast } from "../components/OutcomeToast";
import { OnboardingHint, onboardingDismissed } from "../components/OnboardingHint";
import { useVoiceInput } from "../voice/useVoiceInput";
import { getChatSession, setChatSession } from "./chatSessionStore";
import { Pressable } from "../design/primitives";
import { TurnStatus } from "./TurnStatus";
import { useTurnClock } from "../hooks/useTurnClock";
import { IDLE_TURN, type TurnWait } from "../turnWait";
import { useComposerHeight } from "../hooks/useComposerHeight";
import { composerHeight, shouldSubmitOnKey } from "./composerKeys";
import { Icon } from "../design/icons";
import { ContextSuggestions } from "../components/ContextSuggestions";

/** SPEC-204: superfície do chat — arte de cena, atalhos de lugar e a narrativa. */
export function ChatSurface({ data, log, thinking, busy, blocked, active, onAction, mobile = false, onOpenCombat, onQuoteOffer, offersDisabled }: {
  data: GameResponse | null;
  log: LogEntry[];
  thinking: boolean;
  busy: boolean;
  blocked: boolean;
  active: boolean;
  onAction: (text: string, options?: ActionOptions) => void;
  /** SPEC-216: mobile mostra "Ir para o combate" no chat enquanto o encontro esta ativo. */
  mobile?: boolean;
  onOpenCombat?: () => void;
  /** SPEC-321 R6: cotação de cena/NPC como chip na narração mais recente. */
  onQuoteOffer?: (offer: NonNullable<GameResponse["art_offers"]>[number]) => void;
  offersDisabled?: boolean;
}) {
  const gameId = data?.game_id;
  const fighting = !!data?.combat?.active;
  const simulation = !!data?.combat_simulation?.enabled;
  const interiorsHere = data?.world?.interiors?.here ?? [];
  const exitTo = data?.world?.interiors?.exit_to ?? null;
  const showOnboard = !simulation && !blocked && (data?.world?.turn_count ?? 99) <= 1
    && !onboardingDismissed(gameId ?? null);
  const [initialScroll] = useState(() => getChatSession(gameId));

  // R4: a arte de cena recolhe (mobile) ao rolar a história ou depois do 1º beat no mesmo local; um toque
  // alterna e vale até mudar de local. Sem animação de altura (troca de classe), logo seguro com reduced-motion.
  const sceneKey = data?.visual?.scene?.location_id ?? data?.current_location ?? "";
  const turnCount = data?.world?.turn_count ?? 0;
  const [entry, setEntry] = useState({ key: sceneKey, turn: turnCount });
  const [scrolled, setScrolled] = useState(false);
  if (entry.key !== sceneKey) { setEntry({ key: sceneKey, turn: turnCount }); setScrolled(false); }
  const [override, setOverride] = useState<{ key: string; closed: boolean } | null>(null);
  const autoCollapsed = scrolled || turnCount > entry.turn;
  const artCollapsed = mobile && (override?.key === sceneKey ? override.closed : autoCollapsed);
  const onStoryScroll = useCallback((scrollTop: number, atBottom: boolean, byUser?: boolean) => {
    setChatSession(gameId, { scrollTop, atBottom });
    if (byUser) setScrolled(scrollTop > 24); // o auto-scroll para o fim não conta como "rolar"
  }, [gameId]);
  const offerRef = useRef(onQuoteOffer);
  useEffect(() => { offerRef.current = onQuoteOffer; });
  const stableOffer = useCallback((offer: NonNullable<GameResponse["art_offers"]>[number]) => offerRef.current?.(offer), []);
  const [placesOpen, setPlacesOpen] = useState(false);
  const placeCount = interiorsHere.length + (exitTo ? 1 : 0);

  return (
    <section className="ws-chat" aria-label="Crônica da aventura" hidden={!active}>
      {placeCount > 0 && !fighting && !blocked && (
        <div className="placesbar">
          {mobile && (
            <button type="button" className="placechip placechip--toggle" aria-expanded={placesOpen}
              aria-controls="placesbar-list" onClick={() => setPlacesOpen(open => !open)}>
              Locais daqui <Icon name={placesOpen ? "caret-up" : "caret-down"} />
            </button>
          )}
          {(!mobile || placesOpen) && (
            <div className="placesbar__list" id="placesbar-list">
              {exitTo && (
                <button className="placechip placechip--exit" type="button" disabled={busy}
                        onClick={() => { setPlacesOpen(false); onAction(`Saio para ${exitTo.name}`); }}>
                  <Icon name="exit" /> Sair para {exitTo.name}
                </button>
              )}
              {interiorsHere.map((i) => (
                <button key={i.id} className="placechip" type="button" disabled={busy}
                        onClick={() => { setPlacesOpen(false); onAction(`Entro em ${i.name}`); }}>
                  <Icon name="place" /> {i.name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      <div className="narrative-stage">
        <SceneArtwork scene={data?.visual?.scene} collapsed={artCollapsed}
          onToggle={mobile ? () => setOverride({ key: sceneKey, closed: !artCollapsed }) : undefined} />
        {/* SPEC-199: chip mecânico do turno (aria-live, sem role="status"). */}
        <OutcomeToast outcome={data?.turn_outcome?.receipt_id ? (data.turn_outcome as TurnOutcome) : null} />
        {(data?.companion_feedback?.length ?? 0) > 0 && (
          <ul className="companion-feedback" aria-live="polite">
            {data?.companion_feedback?.map((line) => <li key={line}>{line}</li>)}
          </ul>
        )}
        {showOnboard && gameId && <OnboardingHint gameId={gameId} compact={mobile} />}
        <StoryLog entries={log} thinking={thinking} active={active}
          initialScroll={initialScroll}
          onScrollPosition={onStoryScroll}
          offers={simulation || data?.game_over ? undefined : data?.art_offers} onOffer={stableOffer} offersDisabled={offersDisabled} />
      </div>
      {mobile && fighting && !blocked && onOpenCombat && (
        <button type="button" className="btn btn--primary ws-chat__combat" onClick={onOpenCombat}>
          Ir para o combate
        </button>
      )}
    </section>
  );
}

/** Composer: sempre visível em todos os modos (R6: Esc no contexto devolve o foco aqui).
 *  O rascunho vive em memória por game_id (R7/R8, §8 P3 — nunca em disco). */
export const Composer = forwardRef<HTMLTextAreaElement, {
  data: GameResponse | null;
  busy: boolean;
  blocked: boolean;
  reactionCardId?: string;
  onAction: (text: string, options?: ActionOptions) => void;
  /** SPEC-216: mobile em outra superficie — composer some e o microfone e liberado. */
  offSurface?: boolean;
  /** SPEC-320: espera do turno (fases, estágio, último erro) e "Tentar de novo". */
  turn?: TurnWait;
  onRetry?: () => void;
}>(function Composer({ data, busy, blocked, reactionCardId, onAction, offSurface = false, turn = IDLE_TURN, onRetry }, inputRef) {
  const gameId = data?.game_id;
  const formRef = useRef<HTMLFormElement>(null);
  const areaRef = useRef<HTMLTextAreaElement | null>(null);
  const composing = useRef(false); // IME: entre compositionstart e compositionend
  useComposerHeight(formRef);
  const elapsed = useTurnClock(busy);
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
  // R5: trocar de superficie com a voz ativa libera o microfone e nao envia nada.
  useEffect(() => { if (offSurface && voiceActive) voice.cancel(); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [offSurface]);
  const gameOver = !!data?.game_over;
  const deathPending = !!data?.death_pending;
  const simulation = !!data?.combat_simulation?.enabled;
  const simulationFinished = simulation && !!data?.combat_simulation?.finished;
  const fighting = !!data?.combat?.active;

  // R10: o textarea cresce até 4 linhas (depois rola) e volta a 1 linha quando esvazia.
  useLayoutEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const cs = getComputedStyle(el);
    const lh = parseFloat(cs.lineHeight) || 24;
    const pad = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom) + parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth);
    el.style.height = `${composerHeight(el.scrollHeight, lh, pad)}px`;
  }, [input]);
  const setAreaRef = (node: HTMLTextAreaElement | null) => {
    areaRef.current = node;
    if (typeof inputRef === "function") inputRef(node);
    else if (inputRef) inputRef.current = node;
  };

  function submit(e?: React.FormEvent) {
    e?.preventDefault();
    if (busy || blocked) return;
    const text = input.trim();
    if (!text) return;
    // Explicit text submission cancels any outstanding capture/transcript.
    if (voiceActive) voice.cancel();
    setInput("");
    onAction(text, { reaction_card_id: reactionCardId });
  }

  return (
    <form ref={formRef} className={"actionbar ws-composer" + (offSurface ? " is-offsurface" : "")} onSubmit={submit}>
      <TurnStatus key={turn.seq} phases={turn.ledger.phases} current={turn.ledger.current}
        elapsedMs={turn.gotChunk ? 0 : elapsed} stage={turn.stage} lastError={turn.error}
        onRetry={() => onRetry?.()}
        onFocusInput={() => { if (inputRef && typeof inputRef !== "function") inputRef.current?.focus(); }} />
      <ContextSuggestions data={data} disabled={blocked || busy || offSurface || fighting || gameOver || deathPending || simulation}
        onPick={(text) => { setInput(text); areaRef.current?.focus(); }} />
      <div className="actionbar__composer">
      <textarea
        ref={setAreaRef}
        rows={1}
        id="composer"
        aria-label="Sua ação"
        autoComplete="off"
        enterKeyHint="send"
        disabled={blocked}
        onCompositionStart={() => { composing.current = true; }}
        onCompositionEnd={() => { composing.current = false; }}
        onKeyDown={(e) => {
          if (!shouldSubmitOnKey({ key: e.key, shiftKey: e.shiftKey, altKey: e.altKey, ctrlKey: e.ctrlKey, metaKey: e.metaKey,
            isComposing: e.nativeEvent.isComposing, keyCode: e.keyCode, compositionActive: composing.current })) return;
          e.preventDefault();
          submit();
        }}
        placeholder={
          gameOver
            ? "Memorial — a crônica permanece."
            : simulationFinished
              ? "Simulação encerrada."
            : deathPending
              ? "A Roda do Abismo aguarda sua escolha."
            : fighting
              ? "O inimigo avança. O que você faz?"
              : "O que você faz?"
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
      {/* SPEC-201 A13 / SPEC-320 R4: nome acessível = texto visível; depois do ack, "Aguardando o narrador". */}
      <Pressable variant="primary" type="submit" effect="chat.pending" disabled={busy || blocked}
        pending={busy} pendingLabel={turn.acked ? "Aguardando o narrador" : undefined}>
        {fighting ? "Lutar" : "Agir"}
      </Pressable>
      </div>
      {simulation && fighting && !blocked && (
        <p className="composer-hint">Texto livre executa um ataque básico; use os controles para ações precisas.</p>
      )}
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
