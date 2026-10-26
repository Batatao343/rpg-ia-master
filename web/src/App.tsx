import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import * as api from "./api";
import { isNativeApp, isAndroidClient } from "./native/platform";
import { playAdapter } from "./purchases";
import { installNativeLifecycle } from "./native/lifecycle";
import { decideBack } from "./native/backPolicy";
import { offChatSurface, returnToChat } from "./workspace/mobileSurface";
import { safeStorage } from "./safeStorage";
import { preparePending, loadPending, clearPending, clearPendingIfOwn, clearOwner as clearPendingOwner, shouldClearPending, type PendingOperation } from "./pendingOperation";
import { clearWorkspaceOwner } from "./workspace/workspaceStorage";
import { forgetAllChatSessions } from "./workspace/chatSessionStore";
import { looksDegraded, speakerFromHistory } from "./lib";
import type { ActionOptions, CombatSimulatorPayload, GameResponse, CreatePayload, LogEntry, SaveSummary } from "./types";
import { Banner, type BannerState } from "./components/Banner";
import { CreateScreen } from "./components/CreateScreen";
import { PlayScreen } from "./components/PlayScreen";
import { SaveScreen } from "./components/SaveScreen";
import { EmberField } from "./components/EmberField";
import { DeathModal } from "./components/DeathModal";
import type { LevelUpPick } from "./components/LevelUpModal";
import { CombatSimulatorScreen } from "./components/CombatSimulatorScreen";
import { AuthScreen, hasEmailActionLink } from "./components/AuthScreen";
import { authErrorMessage } from "./lib/authErrors";
import { errMsg, errRequestId } from "./lib/errorMessages";
import { AccountScreen, shards } from "./components/AccountScreen";

import { ImageQuoteDialog } from "./components/ImageQuoteDialog";
import { GeneratedArtCard } from "./components/GeneratedArtCard";
import { TurnLatencyTracker, reportClientLatency } from "./lib/turnLatency";
import {
  IDLE_TURN, PHASE_TEXTS, ROUTE_TEXTS, addPhase, nextOpening, nextStage,
  type OpeningMemo, type TurnWait,
} from "./turnWait";

/** Logout/troca de dono: pendências, layout do workspace e rascunhos em memória (SPEC-204 R9). */
function clearOwner(owner: string) {
  clearPendingOwner(owner);
  clearWorkspaceOwner(owner);
  forgetAllChatSessions();
}

const LS_KEY = "cronicas_game_id";


export function App() {
  type Screen = "bootstrap" | "auth" | "saves" | "create" | "simulator" | "play" | "account";
  const [screen, setScreen] = useState<Screen>("bootstrap");
  const accountReturn = useRef<Screen>("saves");
  const checkoutReturnRequested = () => ["success", "cancel"].includes(
    new URLSearchParams(window.location.search).get("checkout") || "");
  const [accountBalance, setAccountBalance] = useState<string | null>(null);
  const accountBalanceGeneration = useRef(0);
  const accountBalanceAbort = useRef<AbortController | null>(null);
  const deletionInProgress = useRef(false);
  const [data, setData] = useState<GameResponse | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [turn, setTurn] = useState<TurnWait>(IDLE_TURN);
  const turnToken = useRef(0);
  const retryBypass = useRef(false);
  const retrying = useRef(false);
  const openingMemo = useRef<OpeningMemo>({ gid: "", seen: false, loc: "" });
  const resetTurn = useCallback(() => setTurn(t => ({ ...IDLE_TURN, seq: t.seq })), []);
  const [banner, setBanner] = useState<BannerState | null>(null);
  const clearBanner = useCallback(() => setBanner(null), []);
  const [continueData, setContinueData] = useState<GameResponse | null>(null);
  const [saves, setSaves] = useState<SaveSummary[]>([]);
  const [authError, setAuthError] = useState("");
  const [authErrorId, setAuthErrorId] = useState<string | undefined>(undefined);
  const [authNotice, setAuthNotice] = useState("");
  const [authConfig, setAuthConfig] = useState<api.AuthConfig>();
  const [authRequired, setAuthRequired] = useState(false);
  const [imageQuote, setImageQuote] = useState<{ quote: api.ImageQuote; gameId: string; session: number; actionId: string } | null>(null);
  const [imageBusy, setImageBusy] = useState(false);
  const [imageError, setImageError] = useState("");

  function resetImageQuote() {
    setImageQuote(null);
    setImageBusy(false);
    setImageError("");
  }

  const gameId = useRef<string | null>(safeStorage.get(LS_KEY));
  const logSeq = useRef(0);
  const volatileWarned = useRef(false);
  const session = useRef(0);
  const owner = useRef('legacy');
  const [pending, setPending] = useState<PendingOperation | null>(null);
  useEffect(() => {
    const expired = () => {
      if (deletionInProgress.current) return;
      session.current++;
      resetImageQuote();
      setBusy(false); setThinking(false); setData(null); setLog([]);
      setAccountBalance(null);
      setScreen("auth");
    };
    window.addEventListener('rpg:auth-expired', expired);
    return () => window.removeEventListener('rpg:auth-expired', expired);
  }, []);

  // SPEC-193: Android back/resume. Latest-state ref so the listeners registered once never go stale.
  const nativeCtx = useRef({ screen: "bootstrap" as Screen, busy: false, pending: null as PendingOperation | null, hasSaves: false });
  nativeCtx.current = { screen, busy, pending, hasSaves: saves.length > 0 };
  const resumeBusy = useRef(false);
  useEffect(() => {
    let dispose: () => void = () => {};
    let cancelled = false;
    void installNativeLifecycle({
      onBack: () => decideBack(nativeCtx.current.screen, nativeCtx.current.busy, !!nativeCtx.current.pending, offChatSurface()),
      onBackToChat: () => { returnToChat(); },
      onBackNavigate: () => setScreen(nativeCtx.current.screen === "account" ? accountReturn.current : (nativeCtx.current.hasSaves ? "saves" : "create")),
      onResume: () => { void resumeSession(); },
    }).then(d => { if (cancelled) d(); else dispose = d; }).catch(() => {});
    return () => { cancelled = true; dispose(); };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- deps deliberadas: o efeito deve reexecutar só nestas chaves (callbacks/valores recriados a cada render não podem disparar de novo)
  }, []);

  // Resume never re-sends: it re-validates the cookie session and reconciles a persisted pending
  // operation by its operation_id (server idempotency, SPEC-111/141), exactly like a reload.
  async function resumeSession() {
    if (resumeBusy.current) return;
    resumeBusy.current = true;
    try {
      const config = await api.getAuthConfig();
      if (config.required && !config.authenticated) { window.dispatchEvent(new Event('rpg:auth-expired')); return; }
      // SPEC-194: re-send unconsumed Play purchases (idempotent /verify; recovers process death).
      if (isAndroidClient()) void playAdapter(api.googlePlayBackend).restorePending().catch(() => {});
      const gid = gameId.current, user = owner.current;
      if (nativeCtx.current.screen !== "play" || !gid || nativeCtx.current.busy) return;
      const saved = loadPending(user, gid);
      if (!saved) return;
      const status = await api.getOperation(gid, saved.operation_id);
      if (status.status === "completed") {
        clearPending(user, gid); setPending(null);
        setData(await api.getState(gid));
        await loadHistory(gid, session.current);
      }
    } catch { /* offline/transient: user can retry; pending stays persisted */ }
    finally { resumeBusy.current = false; }
  }

  const simNoticed = useRef(false);

  // spec polish-sessao (R3): havendo campanhas salvas, a tela inicial as lista.
  useEffect(() => {
    let active = true;
    async function bootstrapSession() {
      try {
        let config = await api.getAuthConfig();
        // SPEC-193: native app restart drops session cookies; the persistent refresh cookie
        // revives it. Exactly ONE refresh attempt, then re-check config; never loops.
        if (isNativeApp() && config.required && !config.authenticated && await api.refreshSessionOnce()) {
          config = await api.getAuthConfig();
        }
        if (!active) return;
        setAuthRequired(config.required);
        setAuthConfig(config);
        owner.current = config.user_id || "legacy";
        if (hasEmailActionLink) {
          clearOwner(owner.current);
          safeStorage.remove(LS_KEY);
          gameId.current = null;
          setPending(null);
          setScreen("auth");
          return;
        }
        if (config.required && !config.authenticated) {
          setScreen("auth");
          return; // não chama rotas protegidas antes do login
        }
        if (config.authenticated) {
          void refreshBalance(config.user_id || "legacy", session.current);
          // SPEC-194: cold start after process death — re-send unconsumed Play purchases (idempotent).
          if (isAndroidClient()) void playAdapter(api.googlePlayBackend).restorePending().catch(() => {});
        }
      } catch {
        // Compatibilidade com API legacy anterior à rota /auth/config.
      }
      try {
        const list = await api.getSaves();
        if (!active) return;
        setSaves(list);
        accountReturn.current = list.length > 0 ? "saves" : "create";
        setScreen(checkoutReturnRequested() ? "account" : accountReturn.current);
      } catch {
        // API antiga/sem saves — mantém o fluxo clássico de "continuar última".
        const saved = safeStorage.get(LS_KEY);
        if (!saved) { if (active) setScreen("create"); return; }
        try {
          const response = await api.getState(saved);
          if (active) { setContinueData(response); setScreen("create"); }
        } catch {
          safeStorage.remove(LS_KEY);
          if (active) setScreen("create");
        }
      }
    }
    void bootstrapSession();
    return () => { active = false; };
  }, []);

  async function completeAuthenticatedSession() {
      deletionInProgress.current = false;
      const config = await api.getAuthConfig();
      if (!config.authenticated) throw new Error("Sessão não confirmada.");
      setAuthConfig(config);
      const nextOwner = config.user_id || "legacy";
      if (owner.current !== nextOwner) clearOwner(owner.current);
      owner.current = nextOwner;
      session.current++;
      resetImageQuote();
      setPending(null);
      const list = await api.getSaves();
      setSaves(list);
      accountReturn.current = list.length ? "saves" : "create";
      setScreen(checkoutReturnRequested() ? "account" : accountReturn.current);
      void refreshBalance(nextOwner, session.current);
  }

  async function handleLogin(email: string, password: string, create: boolean, captchaToken?: string) {
    setBusy(true);
    setAuthError(""); setAuthErrorId(undefined); setAuthNotice("");
    try {
      const result = await (create ? api.signup(email, password, captchaToken) : api.login(email, password, captchaToken));
      if (!result.authenticated) {
        setAuthNotice(result.message || "Se o endereço puder receber mensagens, enviaremos as instruções.");
        return;
      }
      await completeAuthenticatedSession();
    } catch (error) {
      setAuthError(authErrorMessage(error, create ? "signup" : "login"));
      setAuthErrorId(errRequestId(error));
    } finally {
      setBusy(false);
    }
  }

  function handleDeletionStarted() {
    deletionInProgress.current = true;
    accountBalanceAbort.current?.abort();
    accountBalanceGeneration.current++;
    session.current++;
    resetImageQuote();
    clearOwner(owner.current);
    owner.current = "legacy";
    setPending(null);
    safeStorage.remove(LS_KEY);
    gameId.current = null;
    setData(null); setContinueData(null); setLog([]);
    setBanner(null); resetTurn(); setThinking(false);
    setAccountBalance(null); setSaves([]);
    setAuthConfig(previous => previous ? { ...previous, authenticated: false, user_id: undefined } : previous);
    const url = new URL(window.location.href);
    url.searchParams.delete("checkout"); url.searchParams.delete("order_id");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    setAuthError("");
  }

  function handleAccountDeleted() {
    setAuthNotice("Exclusão da conta iniciada. Seus dados de jogo não estão mais disponíveis.");
    setScreen("auth");
  }

  function handleDeletionRecoveryRequired() {
    deletionInProgress.current = false;
    setAuthNotice("Entre novamente para verificar ou retomar a exclusão da conta.");
    setScreen("auth");
  }

  async function handleLogout() {
    setBusy(true);
    try {
      await api.logout();
      deletionInProgress.current = false;
      session.current++;
      resetImageQuote();
      clearOwner(owner.current);
      setPending(null);
      safeStorage.remove(LS_KEY);
      gameId.current = null;
      setData(null);
      setLog([]);
      setAccountBalance(null);
      setSaves([]);
      setScreen("auth");
    } catch (error) {
      setBanner({ msg: "Não foi possível encerrar a sessão: " + errMsg(error), kind: "error", requestId: errRequestId(error) });
    } finally {
      setBusy(false);
    }
  }

  function pushLog(text: string, role: "player" | "narrator", type: LogEntry["type"]) {
    setLog((prev) => [...prev, { id: logSeq.current++, text, role, type }]);
  }

  async function refreshBalance(expectedOwner: string, generation: number) {
    const balanceGeneration = ++accountBalanceGeneration.current;
    accountBalanceAbort.current?.abort();
    const abort = new AbortController();
    accountBalanceAbort.current = abort;
    try {
      const balance = await api.getAccountBalance(abort.signal);
      if (owner.current === expectedOwner && session.current === generation
          && accountBalanceGeneration.current === balanceGeneration)
        setAccountBalance(balance.available_milli);
    } catch {
      if (owner.current === expectedOwner && session.current === generation
          && accountBalanceGeneration.current === balanceGeneration) setAccountBalance(null);
    } finally {
      if (accountBalanceAbort.current === abort) accountBalanceAbort.current = null;
    }
  }

  function syncAccountBalance(availableMilli: string) {
    accountBalanceGeneration.current++;
    setAccountBalance(availableMilli);
  }

  /** SPEC-320 R11: a narração abre capítulo (capitular)? 1ª da sessão ou 1ª após trocar de local. */
  function markOpening(r: GameResponse): boolean {
    const next = nextOpening(openingMemo.current, r.game_id || gameId.current || "",
      r.world?.location_id || r.world?.location || "", r.message ?? "");
    openingMemo.current = next.memo;
    return next.opening;
  }

  function onTurn(r: GameResponse): number {
    const generation = session.current;
    const entryId = logSeq.current++;
    gameId.current = r.game_id || gameId.current;
    if (gameId.current) safeStorage.set(LS_KEY, gameId.current);

    const opening = markOpening(r);
    // Cria entrada com streaming=true, que ativa efeito typewriter
    setLog((prev) => [
      ...prev,
      { id: entryId, text: r.message, role: "narrator", type: r.message_type || "STORY", speaker: r.speaker ?? null,
        streaming: true, visual: r.visual?.cue, opening,
        // Fim REAL da animação (SPEC-235 R7), não um timer fixo que corta textos longos.
        onTypewriterDone: () => {
          if (session.current !== generation) return;
          setLog(p => p.map(entry => entry.id === entryId
            ? { ...entry, streaming: false, onTypewriterDone: undefined } : entry));
        } }
    ]);

    setData(r);
    if (!r.combat_simulation?.enabled && r.simulated && !simNoticed.current) {
      simNoticed.current = true;
      setBanner({
        msg: "Modo simulado: história fictícia para testar a interface. Adicione GOOGLE_API_KEY no .env para a IA real.",
        kind: "warn",
      });
    } else if (!r.simulated && looksDegraded(r.message)) {
      setBanner({
        msg: "Modo degradado: defina GOOGLE_API_KEY no .env para o narrador responder de verdade.",
        kind: "warn",
      });
    }
    return entryId;
  }

  async function openImageQuote(id: string, type: api.ImageQuote["type"] = "player", reformulation = false, offerId?: string) {
    const generation = session.current;
    setImageBusy(true); setImageError("");
    try {
      const quote = await api.requestImageQuote(id, type, reformulation, offerId);
      if (session.current === generation) setImageQuote({ quote, gameId: id, session: generation, actionId: crypto.randomUUID() });
    } catch (error) {
      if (session.current === generation) setBanner({ msg: "Cotação indisponível: " + errMsg(error), kind: "warn", requestId: errRequestId(error) });
    } finally { if (session.current === generation) setImageBusy(false); }
  }

  async function confirmImageQuote() {
    const current = imageQuote;
    if (!current || imageBusy || current.session !== session.current) return;
    setImageBusy(true); setImageError("");
    try {
      const art = await api.confirmPlayerArt(current.gameId, current.actionId, current.quote.quote_id);
      if (session.current !== current.session) return;
      setData(prev => prev?.game_id === current.gameId ? {
        ...prev,
        portrait_generation_id: art.generation_id && current.quote.type === "player"
          ? art.generation_id : prev.portrait_generation_id,
        art_generations: art.art_generations ?? prev.art_generations,
        art_offers: art.art_offers ?? prev.art_offers,
      } : prev);
      setImageQuote(null);
      setBanner({ msg: "Imagem confirmada. O saldo foi reservado e a geração será processada.", kind: "info" });
      if (authRequired) void refreshBalance(owner.current, current.session);
    } catch (error) {
      if (session.current === current.session) setImageError("Não foi possível confirmar: " + errMsg(error));
    } finally { if (session.current === current.session) setImageBusy(false); }
  }

  async function handleCreate(payload: CreatePayload) {
    if (busy) return;
    setBusy(true);
    const generation = ++session.current;
    resetImageQuote();
    setScreen("play");
    setLog([]);
    setThinking(true);
    try {
      const r = await api.newGame(payload);
      if (session.current !== generation) return;
      onTurn(r);
      if (payload.generate_portrait && r.game_id) {
        void openImageQuote(r.game_id);

      }
    } catch (err) {
      if (session.current !== generation) return;
      setScreen("create");
      setBanner({ msg: "Falha ao criar personagem: " + errMsg(err), kind: "error", requestId: errRequestId(err) });
    } finally {
      if (session.current === generation) { setThinking(false); setBusy(false); }
    }
  }

  async function handleCreateSimulation(payload: CombatSimulatorPayload) {
    if (busy) return;
    const generation = ++session.current;
    resetImageQuote();
    setBusy(true);
    setThinking(true);
    setScreen("play");
    setLog([]);
    try {
      const response = await api.newCombatSimulator(payload);
      if (session.current !== generation) return;
      onTurn(response);
    } catch (err) {
      if (session.current !== generation) return;
      setScreen("simulator");
      setBanner({ msg: "Falha ao abrir a arena: " + errMsg(err), kind: "error", requestId: errRequestId(err) });
    } finally {
      if (session.current === generation) { setThinking(false); setBusy(false); }
    }
  }

  // spec streaming-turno-sse (R4): chunks do servidor alimentam UMA entrada
  // "streaming" do log; o typewriter revela o texto conforme ele cresce.
  const streamEntryId = useRef<number | null>(null);
  const pendingVisual = useRef<GameResponse["visual"] | null>(null);

  /** O id da entrada de stream é alocado de forma SÍNCRONA (o updater do setLog roda depois): evita perder
   *  `replace`/erro que chegam no mesmo tick do primeiro chunk. */
  function ensureStreamId(): number {
    if (streamEntryId.current === null) streamEntryId.current = logSeq.current++;
    return streamEntryId.current;
  }

  function attachStreamVisual(visual: GameResponse["visual"]) {
    pendingVisual.current = visual;
    if (!visual.cue) return;
    const id = ensureStreamId();
    setLog((prev) => {
      const idx = prev.findIndex((e) => e.id === id);
      if (idx >= 0) {
        const entry = prev[idx];
        return [...prev.slice(0, idx), { ...entry, visual: visual.cue }, ...prev.slice(idx + 1)];
      }
      return [...prev, { id, text: "", role: "narrator" as const,
        type: "STORY" as const, streaming: true, visual: visual.cue }];
    });
  }

  /** SPEC-316: `replace` traz o texto final INTEIRO (guard/recibo mudou a prosa); nunca anexa. */
  function replaceStreamText(text: string) {
    const id = streamEntryId.current;
    if (id === null) return;
    setLog((prev) => prev.map((e) => (e.id === id ? { ...e, text } : e)));
  }

  /** SPEC-319: o servidor pediu para descartar o parcial (fallback de provider): recomeça a entrada. */
  function resetStreamText() {
    const id = streamEntryId.current;
    if (id === null) return;
    setLog((prev) => prev.map((e) => (e.id === id ? { ...e, text: "" } : e)));
  }

  function appendChunk(chunk: string, done: boolean, live: boolean = false) {
    if (done) return;
    setTurn(t => (t.gotChunk ? t : { ...t, gotChunk: true }));
    const id = ensureStreamId();
    setLog((prev) => {
      const idx = prev.findIndex((e) => e.id === id);
      if (idx < 0) {
        return [...prev, { id, text: chunk, role: "narrator" as const,
          type: "STORY" as const, streaming: true, live, visual: pendingVisual.current?.cue }];
      }
      const entry = prev[idx];
      return [...prev.slice(0, idx),
        { ...entry, text: entry.text + chunk, live: entry.live || live }, ...prev.slice(idx + 1)];
    });
  }

  function finishStreamEntry(r: GameResponse): number | null {
    const id = streamEntryId.current;
    streamEntryId.current = null;
    const opening = id === null ? false : markOpening(r);
    setLog((prev) => {
      const idx = id === null ? -1 : prev.findIndex((e) => e.id === id);
      if (idx < 0) return prev; // nenhum chunk chegou — onTurn cuida
      const entry = prev[idx];
      return [
        ...prev.slice(0, idx),
        { ...entry, text: r.message, type: r.message_type || "STORY", speaker: r.speaker ?? null, streaming: false,
          visual: entry.visual ?? r.visual?.cue, opening, unsaved: false },
        ...prev.slice(idx + 1),
      ];
    });
    pendingVisual.current = null;
    return id;
  }

  async function refreshTurnCost(gid: string, operationId: string, entryId: number | null,
                                 generation: number, expectedOwner: string) {
    if (entryId === null || !authRequired) return;
    try {
      const result = await api.getTurnCost(gid, operationId);
      if (session.current !== generation || owner.current !== expectedOwner || gameId.current !== gid) return;
      if (result.history_id) setLog(prev => prev.map(entry => entry.id === entryId
        ? { ...entry, historyId: result.history_id ?? undefined, costMilli: result.cost_milli,
            technicalCostUsd: result.technical_cost_usd, technicalCostExact: result.technical_cost_exact } : entry));
    } catch { /* optional read model: story remains visible */ }
    void refreshBalance(expectedOwner, generation);
  }

  async function handleAction(text: string, options: ActionOptions = {}) {
    const bypass = retryBypass.current; retryBypass.current = false; // retry de stream pendurado: `busy` do closure é velho
    if ((busy && !bypass) || !text.trim() || !gameId.current) return;
    const gid = gameId.current, generation = session.current, user = owner.current;
    const token = ++turnToken.current; // "Tentar de novo" que recupera o turno invalida este fluxo (sem duplicar)
    const active = () => session.current === generation && gameId.current === gid && turnToken.current === token;
    setBusy(true); setThinking(true);
    setTurn(t => ({ ...IDLE_TURN, seq: t.seq + 1, stage: nextStage("idle", "submit") }));
    try {
      const old = loadPending(user, gid);
      if (old && old.payload.input_text !== text) throw new Error("Resolva a ação pendente antes de enviar outra.");
      const operation = await preparePending(user, gid, text, { ...options });
      setPending(operation);
      if (operation.volatile && !volatileWarned.current) {
        volatileWarned.current = true;
        setBanner({ msg: "O armazenamento do navegador está bloqueado: sua retomada não sobrevive a recarga.", kind: "warn" });
      }
      const requestOptions = { ...operation.payload, action_id: operation.operation_id } as ActionOptions;
      const status = await api.getOperation(gid, operation.operation_id);
      if (status.status === "completed") {
        clearPending(user, gid);
        if (active()) {
          setPending(null);
          const restored = await api.getState(gid);
          if (!active()) return;
          setData(restored);
          await loadHistory(gid, generation);
        }
        return;
      }
      if (status.status === "running") throw new Error("Esta ação ainda está sendo processada. Consulte novamente em instantes.");
      pendingVisual.current = null;
      // Retry depois de "não salvo": remove a narração órfã e o eco da ação (o mesmo action_id volta a rodar).
      setLog(prev => {
        const at = prev.findIndex(e => e.unsaved);
        if (at < 0) return prev;
        const echo = at > 0 && prev[at - 1].role === "player" ? at - 1 : at;
        return [...prev.slice(0, echo), ...prev.slice(at + 1)];
      });
      // P1-1: um fluxo antigo (já invalidado) nunca apaga o pending de um turno mais novo.
      const clearOwnPending = () => { clearPendingIfOwn(user, gid, operation.operation_id); };
      pushLog(operation.payload.input_text, "player", "STORY");
      setTurn(t => ({ ...t, ledger: addPhase(t.ledger, PHASE_TEXTS.campaign_manager) }));
      let hadChunks = false;
      const latency = new TurnLatencyTracker(operation.operation_id, "stream");
      const reportLatency = () => void reportClientLatency(latency.summary(), api.sendClientLatency);
      try {
        latency.submit();
        const r = await api.sendActionStream(operation.payload.input_text, gid, {
          onAck: () => { latency.firstBytes(); if (active()) setTurn(t => ({ ...t, acked: true })); },
          onEvent: (name, payload) => latency.event(name, payload),
          onPhase: node => { if (active()) setTurn(t => ({ ...t, ledger: addPhase(t.ledger, PHASE_TEXTS[node] ?? null) })); },
          onRoute: route => {
            if (active()) setTurn(t => ({ ...t, ledger: addPhase(t.ledger, ROUTE_TEXTS[route] ?? PHASE_TEXTS.storyteller) }));
          },
          onVisual: visual => { if (active()) attachStreamVisual(visual); },
          onChunk: (chunk, done, live) => {
            if (active()) {
              if (!done) hadChunks = true;
              // SPEC-316: `done` = narração entregue, turno ainda NÃO salvo → selo "registrando…" até o `state`.
              else if (hadChunks) setTurn(t => ({ ...t, stage: nextStage(t.stage, "narrative-done") }));
              appendChunk(chunk, done, live);
            }
          },
          onReset: () => { if (active()) resetStreamText(); },
          onReplace: text => { if (active()) replaceStreamText(text); },
        }, requestOptions);
        clearOwnPending();
        reportLatency();
        if (!active()) return;
        setPending(null);
        const entryId = hadChunks ? finishStreamEntry(r) : onTurn(r);
        if (hadChunks) setData(r);
        void refreshTurnCost(gid, operation.operation_id, entryId, generation, user);
      } catch (error) {
        if (!active()) return;
        if (error instanceof api.HttpError && error.narrativeShown) {
          // SPEC-316 R5/SPEC-320 R13: a narração JÁ foi mostrada e o turno falhou depois — mantém o texto
          // ("não salvo"), preserva o pending e deixa "Tentar de novo" reenviar com o mesmo action_id.
          // Recusa definitiva (4xx) nunca passa: descarta o pending e esconde o retry.
          const definitive = error.status < 500 && shouldClearPending(error.status, error.code);
          const shown = streamEntryId.current;
          streamEntryId.current = null; pendingVisual.current = null;
          if (shown !== null) setLog(prev => prev.map(e => (e.id === shown ? { ...e, streaming: false, unsaved: true } : e)));
          if (definitive) { clearOwnPending(); setPending(null); }
          else setTurn(t => ({ ...t, stage: nextStage(t.stage, "error-after-narration") }));
          throw error;
        }
        if (error instanceof api.HttpError && error.status < 500) {
          // A definitive refusal can never be retried as-is: release the input (SPEC-235 R2).
          if (shouldClearPending(error.status, error.code)) {
            clearOwnPending(); setPending(null);
            // Preserva status/code (SPEC-205 R9: `invalid_target` refaz a mira com o estado novo).
            throw new api.HttpError(error.status, error.code,
              error.message + " A ação pendente foi descartada; você pode enviar uma nova.");
          }
          throw error;
        }
        const orphan = streamEntryId.current;
        streamEntryId.current = null; pendingVisual.current = null;
        if (orphan !== null) setLog(prev => prev.filter(e => e.id !== orphan));
        const post = new TurnLatencyTracker(operation.operation_id, "post");
        post.submit();
        const r = await api.sendAction(operation.payload.input_text, gid, requestOptions);
        post.completePost();
        void reportClientLatency(post.summary(), api.sendClientLatency);
        clearOwnPending();
        if (active()) { setPending(null); const entryId = onTurn(r);
          void refreshTurnCost(gid, operation.operation_id, entryId, generation, user); }
      }
    } catch (error) {
      if (active()) {
        const failure: BannerState = { msg: "Ação não confirmada: " + errMsg(error), kind: "error", requestId: errRequestId(error) };
        setBanner(failure);
        setTurn(t => ({ ...t, error: failure })); // o último erro fica na linha de status até o próximo turno (R10)
      }
      // SPEC-205 R9: alvo velho — refaz a mira com o estado novo do servidor.
      if (error instanceof api.HttpError && error.code === "invalid_target" && active()) {
        try { const fresh = await api.getState(gid); if (active()) setData(fresh); } catch { /* o banner já explica */ }
      }
    } finally {
      if (active()) {
        setThinking(false); setBusy(false);
        // state (ou erro sem narração) destrava; só "falhou depois da narração" permanece para o retry.
        setTurn(t => (t.stage === "failed-after-narration" ? t : { ...IDLE_TURN, seq: t.seq, error: t.error }));
      }
    }
  }


  /** "Tentar de novo" (SPEC-320 R3/R13): reaproveita o pending por operation_id — nunca cria envio novo. */
  async function retryTurn() {
    const gid = gameId.current;
    if (!gid || retrying.current) return; // F-2: duplo clique enquanto getOperation voa
    retrying.current = true;
    try { await retryTurnInner(gid); } finally { retrying.current = false; }
  }

  async function retryTurnInner(gid: string) {
    const pending = loadPending(owner.current, gid);
    if (!pending) return;
    if (!busy) { void handleAction(pending.payload.input_text); return; }
    // Turno ainda em voo: pergunta ao servidor pelo mesmo operation_id em vez de reenviar.
    try {
      const status = await api.getOperation(gid, pending.operation_id);
      if (status.status === "completed") {
        const generation = session.current;
        turnToken.current++; // o fluxo SSE ainda em voo passa a ser ignorado
        streamEntryId.current = null; pendingVisual.current = null;
        clearPending(owner.current, gid); setPending(null);
        const restored = await api.getState(gid);
        if (session.current !== generation || gameId.current !== gid) return;
        setData(restored);
        await loadHistory(gid, generation); // só destrava depois do histórico (o setLog dele não pisa em ação nova)
        if (session.current === generation) { resetTurn(); setThinking(false); setBusy(false); }
      } else if (status.status === "running") {
        setBanner({ msg: "O turno ainda está em andamento no servidor; continue esperando.", kind: "info" });
      } else {
        // `unknown`/`failed`: o fluxo está pendurado. Abandona o SSE e repete o MESMO action_id (idempotente).
        turnToken.current++;
        streamEntryId.current = null; pendingVisual.current = null;
        // F-3: some a narração em voo e o eco do envio abandonado (o reenvio empurra o seu).
        setLog(prev => {
          const kept = prev.filter(e => e.role !== "narrator" || !e.streaming);
          const echo = kept.map(e => e.role === "player" && e.text === pending.payload.input_text).lastIndexOf(true);
          return echo < 0 ? kept : [...kept.slice(0, echo), ...kept.slice(echo + 1)];
        });
        setThinking(false); setBusy(false); resetTurn();
        setBanner({ msg: "O turno não respondeu; reenviando a mesma ação.", kind: "warn" });
        retryBypass.current = true;
        void handleAction(pending.payload.input_text);
      }
    } catch (error) {
      setBanner({ msg: "Não consegui consultar o turno: " + errMsg(error), kind: "warn", requestId: errRequestId(error) });
    }
  }

  function discardPending() {
    const gid = gameId.current;
    if (!gid) return;
    clearPending(owner.current, gid);
    setPending(null);
    resetTurn();
    setBanner({ msg: "Ação pendente descartada. Você pode enviar uma nova ação.", kind: "warn" });
  }

  async function loadHistory(gid: string, generation: number) {
    const entries = new Map<string, api.HistoryEntry>();
    let cursor: string | undefined;
    do {
      const page = await api.getHistory(gid, cursor);
      if (session.current !== generation) return;
      page.entries.forEach(entry => entries.set(entry.id, entry));
      cursor = page.next_cursor || undefined;
      if (page.partial_history) setBanner({ msg: "Este save antigo contém apenas o trecho de histórico preservado.", kind: "warn" });
    } while (cursor);
    if (session.current === generation) setLog([...entries.values()].map(entry => ({
      ...entry, historyId: entry.id, costMilli: entry.cost_milli, speaker: speakerFromHistory(entry),
      technicalCostUsd: entry.technical_cost_usd, technicalCostExact: entry.technical_cost_exact,
      id: logSeq.current++,
    })));
  }

  function handleContinue() {
    if (continueData?.game_id) void handleContinueSave(continueData.game_id);
  }

  async function handleContinueSave(gid: string) {
    if (busy) return;
    const generation = ++session.current;
    resetImageQuote(); resetTurn();
    setBusy(true);
    try {
      const r = await api.getState(gid);
      if (session.current !== generation) return;
      gameId.current = gid;
      safeStorage.set(LS_KEY, gid);
      setScreen("play"); setLog([]); setData(r);
      const saved = loadPending(owner.current, gid);
      setPending(saved);
      if (saved) {
        const status = await api.getOperation(gid, saved.operation_id);
        if (session.current !== generation) return;
        if (status.status === "completed") { clearPending(owner.current, gid); setPending(null); }
      }
      await loadHistory(gid, generation);
    } catch (err) {
      if (session.current === generation) setBanner({ msg: "Não consegui abrir a campanha: " + errMsg(err), kind: "error", requestId: errRequestId(err) });
    } finally {
      if (session.current === generation) setBusy(false);
    }
  }

  async function handleDeleteSave(gid: string) {
    if (busy) return;
    setBusy(true);
    try {
      await api.deleteSave(gid);
      if (gameId.current === gid) {
        gameId.current = null;
        safeStorage.remove(LS_KEY);
      }
      const list = await api.getSaves();
      setSaves(list);
      if (list.length === 0) setScreen("create");
    } catch (err) {
      setBanner({ msg: "Não consegui excluir: " + errMsg(err), kind: "error", requestId: errRequestId(err) });
    } finally {
      setBusy(false);
    }
  }

  function handleNew() {
    if (busy) return;
    session.current++;
    resetImageQuote(); resetTurn();
    setPending(null);
    setScreen(data?.combat_simulation?.enabled ? "simulator" : "create");
    setData(null);
  }

  const handleUiError = useCallback((message: string, requestId?: string) => {
    setBanner({ msg: message, kind: "error", requestId });
  }, []);

  // Fase 4.3: equipar/desequipar e recarregar o estado completo (AC/ataque derivam).
  async function handleEquip(pick: { item_id?: string; unequip_slot?: string }) {
    if (busy || !gameId.current) return;
    const generation = session.current, gid = gameId.current;
    setBusy(true);
    try {
      await api.postEquip({ ...pick, game_id: gid });
      const r = await api.getState(gid);
      if (session.current !== generation) return;
      setData(r);
    } catch (err) {
      if (session.current !== generation) return;
      setBanner({ msg: "Não deu para equipar: " + errMsg(err), kind: "error", requestId: errRequestId(err) });
    } finally {
      if (session.current === generation) setBusy(false);
    }
  }

  // SPEC-209 R4/R7: preparar Cartas. Devolve a mensagem do servidor (ou null) para a aba
  // desfazer a mudança otimista; o estado canônico volta sempre do GET.
  async function handlePrepareCards(prepared: string[]): Promise<string | null> {
    if (busy || !gameId.current) return "Aguarde a ação em andamento.";
    const generation = session.current, gid = gameId.current;
    try {
      const done = await api.postPrepareCards({ prepared, game_id: gid });
      try {
        const r = await api.getState(gid);
        if (session.current === generation) setData(r);
      } catch {
        // A preparação já foi gravada: um GET falho não pode virar "recusado" (R13).
        if (session.current === generation) setData((prev) => prev && prev.game_id === gid ? {
          ...prev, player_stats: { ...prev.player_stats, cards: done.cards, prepared_slots: done.prepared_slots } } : prev);
      }
      return null;
    } catch (err) {
      return errMsg(err);
    }
  }

  // Fase 4.1: aplica escolha de level up e mescla o player atualizado no estado.
  async function handleLevelUp(choiceId: string, pick: LevelUpPick) {
    if (busy) return;
    const generation = session.current;
    setBusy(true);
    try {
      const r = await api.postLevelUp({ choice_id: choiceId, ...pick, game_id: gameId.current });
      if (session.current !== generation) return;
      setData((prev) =>
        prev ? { ...prev, player_stats: { ...prev.player_stats, ...r.player_stats } } : prev
      );
    } catch (err) {
      if (session.current !== generation) return;
      setBanner({ msg: "Escolha recusada: " + errMsg(err), kind: "error", requestId: errRequestId(err) });
    } finally {
      if (session.current === generation) setBusy(false);
    }
  }

  // spec checkpoints-morte (D2): resolve a tela de morte (continuar / aceitar).
  async function handleDeathChoice(choice: "continue" | "accept") {
    if (busy) return;
    const generation = session.current;
    setBusy(true);
    try {
      const r = await api.resolveDeath(gameId.current, choice);
      if (session.current !== generation) return;
      setData(r);
      if (r.game_id) await loadHistory(r.game_id, generation);
    } catch (err) {
      if (session.current !== generation) return;
      setBanner({ msg: "A Roda hesitou: " + errMsg(err), kind: "error", requestId: errRequestId(err) });
    } finally {
      if (session.current === generation) setBusy(false);
    }
  }

  // SPEC-321 R6: cotação de retrato + imagens encomendadas moram no painel Personagem (não no topo da tela).
  const artPanel = screen === "play" && data?.game_id ? (
    <div className="art-orders">
      {!data.combat_simulation?.enabled && !data.game_over && (
        <button type="button" className="btn btn--ghost art-orders__quote" disabled={busy || imageBusy}
          onClick={() => void openImageQuote(data.game_id!, "player", Boolean(data.portrait_generation_id))}>
          {data.portrait_generation_id ? "Cotar reformulação" : "Cotar retrato"}
        </button>
      )}
      {(data.art_generations || []).some(row => row.type !== "player") && (
        <div className="image-generations" aria-label="Imagens encomendadas">
          {(data.art_generations || []).filter(row => row.type !== "player").map(row =>
            <GeneratedArtCard key={`${data.game_id}:${row.generation_id}`} gameId={data.game_id}
              generationId={row.generation_id} type={row.type as "npc" | "scene"} />)}
        </div>
      )}
    </div>
  ) : null;
  const confirmLeave = !!pending || turn.stage === "narrated" || turn.stage === "failed-after-narration";

  const renderedOwner = owner.current;
  const renderedSession = session.current;
  return (
    <MotionConfig reducedMotion="user">
      <div className="atmosphere" aria-hidden />
      <EmberField />
      {screen !== "play" && <Banner state={banner} onDone={clearBanner} />}
      {imageQuote && imageQuote.session === session.current && screen === "play" &&
        <ImageQuoteDialog quote={imageQuote.quote} busy={imageBusy} error={imageError}
          onConfirm={() => void confirmImageQuote()} onCancel={() => setImageQuote(null)} />}
      {screen === "play" && pending && <div className={"pending-operation" + (busy ? " is-busy" : "")} role="group" aria-label="Ação pendente">
        {/* SPEC-321: quando o turno falhou depois da narração, a linha de status do compositor já oferece
            "Tentar de novo" — não repete o mesmo botão aqui; fica só o descarte. */}
        {turn.stage !== "failed-after-narration" && (
          <button className="btn btn--primary" type="button" disabled={busy}
            onClick={() => void handleAction(pending.payload.input_text)}>
            Consultar / retomar ação pendente
          </button>
        )}
        <button className="btn btn--ghost pending-operation__discard" type="button" disabled={busy}
          onClick={discardPending}>
          Descartar ação pendente
        </button>
      </div>}
      {authRequired && screen !== "auth" && screen !== "play" && screen !== "account" && (
        <div className="shell-actions">
          {screen !== "bootstrap" && (
            <button className="account-shell-link btn btn--ghost" type="button" disabled={busy}
              onClick={() => { accountReturn.current = screen; setScreen("account"); }}>
              Conta{accountBalance !== null ? ` · ${shards(accountBalance)} Estilhas` : ""}
            </button>
          )}
          <button className="session-logout btn btn--ghost" disabled={busy}
            onClick={() => void handleLogout()}>
            Encerrar sessão
          </button>
        </div>
      )}
      {data?.death_pending && !data?.game_over && !data?.combat_simulation?.enabled && (
        <DeathModal
          busy={busy}
          death={data.death}
          onContinue={() => handleDeathChoice("continue")}
          onAccept={() => handleDeathChoice("accept")}
        />
      )}
      <AnimatePresence mode="wait">
        {screen === "bootstrap" ? (
          <motion.main key="bootstrap" className="create" aria-busy="true"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <p role="status" className="muted">Abrindo as Crônicas…</p>
          </motion.main>
        ) : screen === "auth" ? (
          <motion.div key="auth" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <AuthScreen busy={busy} onLogin={handleLogin} onAuthenticated={completeAuthenticatedSession}
              config={authConfig} error={authError} errorRequestId={authErrorId} notice={authNotice}
              onClearMessages={() => { setAuthError(""); setAuthErrorId(undefined); setAuthNotice(""); }} />
          </motion.div>
        ) : screen === "account" ? (
          <motion.div key="account" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <AccountScreen onBack={() => setScreen(accountReturn.current)}
              captcha={authConfig?.captcha} onBalanceChange={value => {
                if (owner.current === renderedOwner && session.current === renderedSession
                    && !deletionInProgress.current) syncAccountBalance(value);
              }} lifecycleAvailable={authConfig?.lifecycle_available ?? false}
              onDeletionStarted={handleDeletionStarted} onDeleted={handleAccountDeleted}
              onRecoveryRequired={handleDeletionRecoveryRequired} />
          </motion.div>
        ) : screen === "saves" ? (
          <motion.div
            key="saves"
            initial={{ opacity: 0, scale: 0.985 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.01 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            <SaveScreen
              saves={saves}
              busy={busy}
              onContinue={handleContinueSave}
              onDelete={handleDeleteSave}
              onNew={handleNew}
              onSimulate={() => setScreen("simulator")}
              auditExport={authConfig?.lifecycle_available ?? false}
            />
          </motion.div>
        ) : screen === "create" ? (
          <motion.div
            key="create"
            initial={{ opacity: 0, scale: 0.985 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.01 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          >
            <CreateScreen
              busy={busy}
              continueData={continueData}
              onCreate={handleCreate}
              onContinue={handleContinue}
              onSimulate={() => setScreen("simulator")}
              onError={handleUiError}
            />
          </motion.div>
        ) : screen === "simulator" ? (
          <motion.div
            key="simulator"
            initial={{ opacity: 0, scale: 0.985 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.01 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
          >
            <CombatSimulatorScreen
              busy={busy}
              onStart={handleCreateSimulation}
              onBack={() => setScreen(saves.length > 0 ? "saves" : "create")}
              onError={handleUiError}
            />
          </motion.div>
        ) : (
          <motion.div className="play-shell"
            key="play"
            initial={{ y: 10 }}
            animate={{ y: 0 }}
            exit={{ y: 0 }}
            transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          >
            <PlayScreen
              data={data}
              log={log}
              thinking={thinking}
              turn={turn}
              onRetryTurn={retryTurn}
              banner={<Banner state={banner} onDone={clearBanner} />}
              busy={busy}
              onAction={handleAction}
              onNew={handleNew}
              onLevelUp={handleLevelUp}
              onEquip={handleEquip}
              onPrepareCards={handlePrepareCards}
              onLogout={authRequired ? handleLogout : undefined}
              onAccount={authRequired ? () => { accountReturn.current = "play"; setScreen("account"); } : undefined}
              accountBalance={accountBalance}
              confirmLeave={confirmLeave}
              artPanel={artPanel}
              onQuoteOffer={offer => { if (data?.game_id) void openImageQuote(data.game_id, offer.type, false, offer.offer_id); }}
              offersDisabled={busy || imageBusy}
              owner={renderedOwner}
            />
          </motion.div>
        )}
      </AnimatePresence>
      {screen !== "play" && screen !== "bootstrap" && <LegalLinks />}
    </MotionConfig>
  );
}

/** SPEC-197 R3: static legal pages (RASCUNHO until published by the owner). Plain links, no script. */
function LegalLinks() {
  return (
    <footer className="legal-links" aria-label="Documentos legais">
      <a href="/privacidade/">Privacidade</a>
      <a href="/termos/">Termos</a>
      <a href="/reembolso/">Reembolso</a>
      <a href="/suporte/">Suporte</a>
    </footer>
  );
}

