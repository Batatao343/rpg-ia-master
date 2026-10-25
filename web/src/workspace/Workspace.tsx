import { forwardRef, useEffect, useImperativeHandle, useReducer, useRef, useState,
  type CSSProperties, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";
import type { ActionOptions, GameResponse, LogEntry } from "../types";
import type { TurnWait } from "../turnWait";
import { useVitalityHit, type EquipFn } from "../components/Hud";
import { ChatSurface, Composer } from "./ChatSurface";
import { ContextSurface } from "./ContextSurface";
import { MobileTabBar } from "../components/MobileTabBar";
import { SURFACE_LABELS, isMobileViewport, mobileSurface, registerBackBridge, shouldAutoOpenCombat, type Surface } from "./mobileSurface";
import { useVisualViewport } from "./useVisualViewport";
import { getChatSession, setChatSession } from "./chatSessionStore";
import { loadWorkspace, saveWorkspace } from "./workspaceStorage";
import {
  CONTEXT_TABS, DEFAULT_WORKSPACE, MIN_CHAT_PX, MIN_CONTEXT_PX, SPLIT_MIN_VIEWPORT, TAB_LABELS,
  clampRatio, effectiveMode, workspaceReducer, type ContextTab, type WorkspaceState,
} from "./workspaceModel";

const SEPARATOR_PX = 12;

export interface WorkspaceHandle {
  openTab: (tab: ContextTab, options?: { codexSection?: string }) => void;
}

interface Props {
  owner: string;
  data: GameResponse | null;
  log: LogEntry[];
  thinking: boolean;
  /** SPEC-320: espera do turno para a linha de status do compositor. */
  turn?: TurnWait;
  onRetryTurn?: () => void;
  busy: boolean;
  blocked: boolean;
  onAction: (text: string, options?: ActionOptions) => void;
  onEquip?: EquipFn;
  onPrepareCards?: (prepared: string[]) => Promise<string | null>;
  onOpenLevelUp?: () => void;
  /** SPEC-212: desfecho do combate dispensado (elevado ao PlayScreen p/ sequenciar o modal de nível). */
  dismissedResult?: string | null;
  onDismissResult?: (resultEventId: string) => void;
}

function useViewportWidth(): number {
  const [width, setWidth] = useState(() => (typeof window === "undefined" ? 1440 : window.innerWidth));
  useEffect(() => {
    const update = () => setWidth(window.innerWidth);
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  return width;
}

function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el || !el.tagName) return false;
  return el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable;
}

function modalOpen(): boolean {
  return !!document.querySelector('[aria-modal="true"], dialog[open]');
}

/** SPEC-204: chat + UM painel de contexto (`chat` | `split` | `context`). Montado
 *  com `key={game_id}`: layout, rascunho e scroll nunca vazam entre jogos (R8). */
export const Workspace = forwardRef<WorkspaceHandle, Props>(function Workspace(props, ref) {
  const { owner, data, log, thinking, turn, onRetryTurn, busy, blocked, onAction, onEquip } = props;
  const gameId = data?.game_id ?? null;
  const simulation = !!data?.combat_simulation?.enabled;
  const fighting = !!data?.combat?.active;

  const [state, dispatch] = useReducer(workspaceReducer, undefined, (): WorkspaceState => {
    const stored = gameId ? loadWorkspace(owner, gameId) : null;
    if (stored) return stored;
    // R17: o laboratório abre direto no Combate, em split.
    return simulation ? workspaceReducer(DEFAULT_WORKSPACE, { type: "combat_started" }) : DEFAULT_WORKSPACE;
  });
  const viewport = useViewportWidth();
  const single = viewport < SPLIT_MIN_VIEWPORT;
  const mobile = isMobileViewport(viewport);
  const surface: Surface = mobileSurface(state, viewport);
  const keyboardOpen = useVisualViewport(mobile);
  const mode = effectiveMode(state, viewport);
  const chatVisible = mode !== "context";
  const contextVisible = mode !== "chat";

  const [reactionCardId, setReactionState] = useState<string | undefined>(() => getChatSession(gameId).reactionCardId);
  const setReaction = (id?: string) => { setReactionState(id); setChatSession(gameId, { reactionCardId: id }); };
  const [codexSection, setCodexSection] = useState<string | undefined>();
  const [combatEnded, setCombatEnded] = useState(false);
  const hitKey = useVitalityHit(data?.player_stats?.vitalidade);

  const rootRef = useRef<HTMLDivElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLInputElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const [gridWidth, setGridWidth] = useState(0);

  // Abas montam na primeira visita visível e depois só se escondem (R7).
  const [visited, setVisited] = useState<ReadonlySet<ContextTab>>(() => new Set());
  if (contextVisible && !visited.has(state.tab)) setVisited(new Set(visited).add(state.tab));

  useImperativeHandle(ref, () => ({
    openTab(tab, options) {
      if (options?.codexSection) setCodexSection(options.codexSection);
      dispatch({ type: "open_tab", tab, single });
    },
  }), [single]);

  useEffect(() => { if (gameId) saveWorkspace(owner, gameId, state); }, [owner, gameId, state]);

  // Reação selecionada some quando a Carta deixa de estar pronta.
  useEffect(() => {
    const selected = data?.combat?.cards?.find((card) => card.id === reactionCardId);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
    if (reactionCardId && (!selected || !selected.ready)) setReaction(undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.combat?.cards, reactionCardId]);

  // R10 (D2): início de combate abre Combate (nunca terceira coluna); fim mantém a aba.
  // SPEC-216 §8 P4: no mobile, o encontro que COMECA depois da montagem so troca para Combate
  // depois que a narracao do inicio foi renderizada (o botao "Ir para o combate" fica no chat).
  const wasFighting = useRef(false);
  const mounted = useRef(false);
  const [awaitingNarration, setAwaitingNarration] = useState(false);
  useEffect(() => {
    if (fighting && !wasFighting.current) {
      setCombatEnded(false);
      if (mobile && mounted.current) setAwaitingNarration(true);
      else dispatch({ type: "combat_started" });
    }
    if (!fighting && wasFighting.current) {
      setCombatEnded(true); setAwaitingNarration(false); dispatch({ type: "combat_ended" });
    }
    wasFighting.current = fighting;
    mounted.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fighting]);
  const streamingNow = log.some((entry) => entry.streaming);
  useEffect(() => {
    if (!awaitingNarration || !shouldAutoOpenCombat(false, true, !thinking && !streamingNow)) return;
    let second = 0;
    const first = requestAnimationFrame(() => { second = requestAnimationFrame(() => {
      setAwaitingNarration(false); dispatch({ type: "combat_started" });
    }); });
    return () => { cancelAnimationFrame(first); cancelAnimationFrame(second); };
  }, [awaitingNarration, thinking, streamingNow, log]);
  useEffect(() => {
    if (!awaitingNarration) return;
    const timer = setTimeout(() => { setAwaitingNarration(false); dispatch({ type: "combat_started" }); }, 2500);
    return () => clearTimeout(timer);
  }, [awaitingNarration]);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
  useEffect(() => { if (state.tab !== "combate") setCombatEnded(false); }, [state.tab]);

  useEffect(() => {
    const node = gridRef.current;
    if (!node) return;
    const measure = () => setGridWidth(node.getBoundingClientRect().width);
    measure();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  // R6: atalhos globais (só com foco dentro do app; nunca com modal aberto).
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented || modalOpen()) return;
      const mod = event.ctrlKey || event.metaKey;
      if (mod && !event.altKey && event.key === "1") {
        event.preventDefault();
        dispatch(single ? { type: "close_context", single } : { type: "set_mode", mode: "chat" });
        composerRef.current?.focus();
        return;
      }
      if (isTypingTarget(event.target)) return;
      const inside = event.target instanceof Element && !!event.target.closest(".play");
      if (event.altKey && !mod && (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
        if (!inside) return;
        event.preventDefault();
        dispatch({ type: event.key === "ArrowLeft" ? "back" : "forward" });
        return;
      }
      if (mod && !event.altKey && /^[2-6]$/.test(event.key)) {
        event.preventDefault();
        dispatch({ type: "open_tab", tab: CONTEXT_TABS[Number(event.key) - 2], single });
        return;
      }
      if (mod && !event.altKey && event.key === "\\") {
        event.preventDefault();
        dispatch({ type: "toggle_split" });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [single]);

  const usable = Math.max(0, (gridWidth || viewport) - SEPARATOR_PX);
  const ratio = clampRatio(state.ratio, usable);
  const fits = usable >= MIN_CHAT_PX + MIN_CONTEXT_PX;
  const minPct = fits ? Math.round(clampRatio(0, usable) * 100) : 50;
  const maxPct = fits ? Math.round(clampRatio(1, usable) * 100) : 50;

  const [isDragging, setDragging] = useState(false);
  function ratioFromPointer(clientX: number) {
    const rect = gridRef.current?.getBoundingClientRect();
    if (!rect) return;
    const total = rect.width - SEPARATOR_PX;
    dispatch({ type: "set_ratio", ratio: clampRatio((clientX - rect.left - SEPARATOR_PX / 2) / total, total) });
  }
  // Ponteiro: captura no divisor + escuta na janela até soltar (sem inércia).
  function onPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    event.preventDefault();
    const target = event.currentTarget;
    const pointerId = event.pointerId;
    try { target.setPointerCapture(pointerId); } catch { /* ponteiro sintético */ }
    setDragging(true);
    const move = (e: PointerEvent) => ratioFromPointer(e.clientX);
    const up = () => {
      setDragging(false);
      try { target.releasePointerCapture(pointerId); } catch { /* já liberado */ }
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  }
  function onSeparatorKey(event: ReactKeyboardEvent<HTMLDivElement>) {
    const step = event.shiftKey ? 0.1 : 0.05;
    let next: number | null = null;
    if (event.key === "ArrowLeft") next = ratio - step;
    else if (event.key === "ArrowRight") next = ratio + step;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = 1;
    else if (event.key === "Enter") next = 0.5;
    if (next == null || event.altKey) return;
    event.preventDefault();
    dispatch({ type: "set_ratio", ratio: clampRatio(next, usable) });
  }

  const openTab = (tab: ContextTab) => dispatch({ type: "open_tab", tab, single });
  const showChat = () => {
    dispatch(single ? { type: "close_context", single } : { type: "set_mode", mode: "chat" });
  };
  const showContext = () => dispatch(single ? { type: "open_tab", tab: state.tab, single } : { type: "set_mode", mode: "context" });
  const selectSurface = (target: Surface) => { if (target === "chat") showChat(); else openTab(target); };

  // R8: a cada troca de superficie o foco vai ao titulo (nao na montagem inicial).
  const firstSurface = useRef(true);
  useEffect(() => {
    if (firstSurface.current) { firstSurface.current = false; return; }
    if (mobile) titleRef.current?.focus({ preventScroll: true });
  }, [surface, mobile]);
  const surfaceRef = useRef(surface);
  useEffect(() => { surfaceRef.current = surface; });
  const showChatRef = useRef(showChat);
  useEffect(() => { showChatRef.current = showChat; });
  useEffect(() => registerBackBridge({
    offChat: () => mobile && surfaceRef.current !== "chat",
    toChat: () => showChatRef.current(),
  }), [mobile]);

  const p = data?.player_stats;
  const style = { "--ws-ratio": String(ratio) } as CSSProperties;

  const stats = (
    <div className="ws-bar__status">
      <span className="ws-stat ws-stat--hp">Vitalidade <b>{p?.vitalidade ?? 0}/{p?.max_vitalidade ?? 0}</b></span>
      {(p?.max_entropy ?? 0) > 0 && <span className="ws-stat ws-stat--entropy">Entropia <b>{p?.entropy ?? 0}/{p?.max_entropy ?? 0}</b></span>}
      {fighting && <span className="ws-stat ws-stat--fight">em combate</span>}
    </div>
  );

  return (
    <div className={"ws-root" + (mobile ? " ws-root--mobile" : "")} ref={rootRef}>
      {mobile ? (
        <div className="ws-mhead">
          <h2 className="ws-mhead__title" data-testid="surface-title" tabIndex={-1} ref={titleRef}>{SURFACE_LABELS[surface]}</h2>
          {stats}
        </div>
      ) : (
      <div className="ws-bar" role="group" aria-label="Estado e navegação do painel">
        {stats}
        <div className="ws-bar__nav">
          <button type="button" className="iconbtn" aria-label="Voltar para a aba anterior"
            disabled={state.cursor <= 0} onClick={() => dispatch({ type: "back" })}>‹</button>
          <button type="button" className="iconbtn" aria-label="Avançar para a próxima aba"
            disabled={state.cursor >= state.history.length - 1} onClick={() => dispatch({ type: "forward" })}>›</button>
          <div className="ws-modes" role="group" aria-label="Modo de exibição">
            <button type="button" className="iconbtn" aria-pressed={mode === "chat"} onClick={showChat}>Chat</button>
            {!single && <button type="button" className="iconbtn" aria-pressed={mode === "split"}
              onClick={() => dispatch({ type: "set_mode", mode: "split" })}>Dividido</button>}
            <button type="button" className="iconbtn" aria-pressed={mode === "context"} onClick={showContext}
              title={`Painel: ${TAB_LABELS[state.tab]}`}>Painel</button>
          </div>
        </div>
      </div>
      )}

      <div className={`ws ws--${mode}${isDragging ? " is-dragging" : ""}`} data-mode={mode} ref={gridRef} style={style}>
        <ChatSurface data={data} log={log} thinking={thinking}
          busy={busy} blocked={blocked} active={chatVisible} onAction={onAction}
          mobile={mobile} onOpenCombat={() => openTab("combate")} />
        {mode === "split" && (
          // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-noninteractive-tabindex -- separador redimensionável (window splitter) focável com setas, padrão WAI-ARIA
          <div className="ws-sep" role="separator" aria-orientation="vertical" tabIndex={0}
            aria-label="Redimensionar chat e painel" aria-controls="ws-context"
            aria-valuenow={Math.round(ratio * 100)} aria-valuemin={minPct} aria-valuemax={maxPct}
            aria-valuetext={`Chat com ${Math.round(ratio * 100)}% da largura`}
            onPointerDown={onPointerDown} onKeyDown={onSeparatorKey}
            onDoubleClick={() => dispatch({ type: "set_ratio", ratio: 0.5 })} />
        )}
        <div id="ws-context" className="ws-ctx-slot" hidden={!contextVisible}>
          <ContextSurface data={data} active={contextVisible} tab={state.tab} visited={visited}
            busy={busy} blocked={blocked} hitKey={hitKey} combatEnded={combatEnded} mobile={mobile}
            reactionCardId={reactionCardId} onReaction={setReaction}
            codexSection={codexSection} onCodexSection={setCodexSection}
            onSelectTab={openTab} onClose={showChat} onEscape={() => composerRef.current?.focus()}
            onAction={onAction} onEquip={onEquip}
            onPrepareCards={props.onPrepareCards} onOpenLevelUp={props.onOpenLevelUp}
            dismissedResult={props.dismissedResult} onDismissResult={props.onDismissResult} />
        </div>
        <Composer ref={composerRef} data={data} busy={busy} blocked={blocked}
          reactionCardId={reactionCardId} onAction={onAction} offSurface={mobile && surface !== "chat"}
          turn={turn} onRetry={onRetryTurn} />
      </div>
      {mobile && <MobileTabBar surface={surface} fighting={fighting} hidden={keyboardOpen} onSelect={selectSurface} />}
    </div>
  );
});
