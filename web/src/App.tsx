import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import * as api from "./api";
import { preparePending, loadPending, clearPending, clearOwner, type PendingOperation } from "./pendingOperation";
import { looksDegraded } from "./lib";
import type { ActionOptions, CombatSimulatorPayload, GameResponse, CreatePayload, LogEntry, SaveSummary } from "./types";
import { Banner, type BannerState } from "./components/Banner";
import { CreateScreen } from "./components/CreateScreen";
import { PlayScreen } from "./components/PlayScreen";
import { SaveScreen } from "./components/SaveScreen";
import { EmberField } from "./components/EmberField";
import { DeathModal } from "./components/DeathModal";
import type { LevelUpPick } from "./components/LevelUpModal";
import { CombatSimulatorScreen } from "./components/CombatSimulatorScreen";
import { AuthScreen } from "./components/AuthScreen";

const LS_KEY = "cronicas_game_id";

// spec streaming-turno-sse (R4): textos curados por nó/rota do grafo.
const PHASE_TEXTS: Record<string, string> = {
  campaign_manager: "O mestre consulta os arcanos…",
  dm_router: "O mestre decide o rumo…",
  storyteller: "O narrador tece o destino…",
  combat_agent: "⚔️ O aço encontra o aço…",
  npc_actor: "🗣️ Vozes se erguem…",
  loot_agent: "💰 Algo reluz entre os despojos…",
  archivist: "O escriba registra a jornada…",
};
const ROUTE_TEXTS: Record<string, string> = {
  combat_agent: "⚔️ O aço encontra o aço…",
  npc_actor: "🗣️ Vozes se erguem…",
  loot: "💰 Algo reluz entre os despojos…",
  storyteller: "O narrador tece o destino…",
};

export function App() {
  const [screen, setScreen] = useState<"bootstrap" | "auth" | "saves" | "create" | "simulator" | "play">("bootstrap");
  const [data, setData] = useState<GameResponse | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [phaseLabel, setPhaseLabel] = useState<string | null>(null);
  const [banner, setBanner] = useState<BannerState | null>(null);
  const [continueData, setContinueData] = useState<GameResponse | null>(null);
  const [saves, setSaves] = useState<SaveSummary[]>([]);
  const [authError, setAuthError] = useState("");
  const [authRequired, setAuthRequired] = useState(false);

  const gameId = useRef<string | null>(localStorage.getItem(LS_KEY));
  const logSeq = useRef(0);
  const session = useRef(0);
  const owner = useRef('legacy');
  const [pending, setPending] = useState<PendingOperation | null>(null);
  useEffect(() => {
    const expired = () => {
      session.current++;
      setBusy(false); setThinking(false); setData(null); setLog([]);
      setScreen("auth");
    };
    window.addEventListener('rpg:auth-expired', expired);
    return () => window.removeEventListener('rpg:auth-expired', expired);
  }, []);

  const simNoticed = useRef(false);

  // spec polish-sessao (R3): havendo campanhas salvas, a tela inicial as lista.
  useEffect(() => {
    let active = true;
    async function bootstrapSession() {
      try {
        const config = await api.getAuthConfig();
        if (!active) return;
        setAuthRequired(config.required);
        owner.current = config.user_id || "legacy";
        if (config.required && !config.authenticated) {
          setScreen("auth");
          return; // não chama rotas protegidas antes do login
        }
      } catch {
        // Compatibilidade com API legacy anterior à rota /auth/config.
      }
      try {
        const list = await api.getSaves();
        if (!active) return;
        setSaves(list);
        setScreen(list.length > 0 ? "saves" : "create");
      } catch {
        // API antiga/sem saves — mantém o fluxo clássico de "continuar última".
        const saved = localStorage.getItem(LS_KEY);
        if (!saved) { if (active) setScreen("create"); return; }
        try {
          const response = await api.getState(saved);
          if (active) { setContinueData(response); setScreen("create"); }
        } catch {
          localStorage.removeItem(LS_KEY);
          if (active) setScreen("create");
        }
      }
    }
    void bootstrapSession();
    return () => { active = false; };
  }, []);

  async function handleLogin(email: string, password: string, create: boolean) {
    setBusy(true);
    setAuthError("");
    try {
      await (create ? api.signup(email, password) : api.login(email, password));
      const config = await api.getAuthConfig();
      const nextOwner = config.user_id || "legacy";
      if (owner.current !== nextOwner) clearOwner(owner.current);
      owner.current = nextOwner;
      session.current++;
      setPending(null);
      const list = await api.getSaves();
      setSaves(list);
      setScreen(list.length ? "saves" : "create");
    } catch (error) {
      setAuthError(errMsg(error));
    } finally {
      setBusy(false);
    }
  }

  async function handleLogout() {
    setBusy(true);
    try {
      await api.logout();
      session.current++;
      clearOwner(owner.current);
      setPending(null);
      localStorage.removeItem(LS_KEY);
      gameId.current = null;
      setData(null);
      setLog([]);
      setSaves([]);
      setScreen("auth");
    } catch (error) {
      setBanner({ msg: "Não foi possível encerrar a sessão: " + errMsg(error), kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  function pushLog(text: string, role: "player" | "narrator", type: LogEntry["type"]) {
    setLog((prev) => [...prev, { id: logSeq.current++, text, role, type }]);
  }

  function onTurn(r: GameResponse) {
    const generation = session.current;
    const entryId = logSeq.current++;
    gameId.current = r.game_id || gameId.current;
    if (gameId.current) localStorage.setItem(LS_KEY, gameId.current);

    // Cria entrada com streaming=true, que ativa efeito typewriter
    setLog((prev) => [
      ...prev,
      { id: entryId, text: r.message, role: "narrator", type: r.message_type || "STORY", streaming: true, visual: r.visual?.cue }
    ]);

    // Após animação estar completa (300ms), finaliza a entrada
    setTimeout(() => {
      if (session.current !== generation) return;
      setLog(prev => prev.map(entry => entry.id === entryId ? { ...entry, streaming: false } : entry));
    }, 300);

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
  }

  async function handleCreate(payload: CreatePayload) {
    if (busy) return;
    setBusy(true);
    const generation = ++session.current;
    setScreen("play");
    setLog([]);
    setThinking(true);
    try {
      const r = await api.newGame(payload);
      if (session.current !== generation) return;
      onTurn(r);
      if (payload.generate_portrait && r.game_id) {
        void api.confirmPlayerArt(r.game_id, crypto.randomUUID()).then((art) => {
          if (session.current !== generation) return;
          if (art.generation_id) setData(prev => prev?.game_id === r.game_id ? { ...prev, portrait_generation_id: art.generation_id } : prev);
          setBanner({
            msg: art.status === "disabled"
              ? "Retrato dinâmico desativado; a arte-base permanece disponível."
              : "Retrato encomendado. Ele aparecerá quando o processamento terminar.",
            kind: "warn",
          });
        }).catch((error) => {
          if (session.current === generation) setBanner({ msg: "O retrato não foi encomendado: " + errMsg(error), kind: "warn" });
        });
      }
    } catch (err) {
      if (session.current !== generation) return;
      setScreen("create");
      setBanner({ msg: "Falha ao criar personagem: " + errMsg(err), kind: "error" });
    } finally {
      if (session.current === generation) { setThinking(false); setBusy(false); }
    }
  }

  async function handleCreateSimulation(payload: CombatSimulatorPayload) {
    if (busy) return;
    const generation = ++session.current;
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
      setBanner({ msg: "Falha ao abrir a arena: " + errMsg(err), kind: "error" });
    } finally {
      if (session.current === generation) { setThinking(false); setBusy(false); }
    }
  }

  // spec streaming-turno-sse (R4): chunks do servidor alimentam UMA entrada
  // "streaming" do log; o typewriter revela o texto conforme ele cresce.
  const streamEntryId = useRef<number | null>(null);
  const pendingVisual = useRef<GameResponse["visual"] | null>(null);

  function attachStreamVisual(visual: GameResponse["visual"]) {
    pendingVisual.current = visual;
    if (!visual.cue) return;
    setLog((prev) => {
      const id = streamEntryId.current;
      const idx = id === null ? -1 : prev.findIndex((e) => e.id === id);
      if (idx >= 0) {
        const entry = prev[idx];
        return [...prev.slice(0, idx), { ...entry, visual: visual.cue }, ...prev.slice(idx + 1)];
      }
      const nid = logSeq.current++;
      streamEntryId.current = nid;
      return [...prev, { id: nid, text: "", role: "narrator" as const,
        type: "STORY" as const, streaming: true, visual: visual.cue }];
    });
  }

  function appendChunk(chunk: string, done: boolean) {
    if (done) return;
    setLog((prev) => {
      const id = streamEntryId.current;
      const idx = id === null ? -1 : prev.findIndex((e) => e.id === id);
      if (idx < 0) {
        const nid = logSeq.current++;
        streamEntryId.current = nid;
        return [...prev, { id: nid, text: chunk, role: "narrator" as const,
          type: "STORY" as const, streaming: true, visual: pendingVisual.current?.cue }];
      }
      const entry = prev[idx];
      return [...prev.slice(0, idx), { ...entry, text: entry.text + chunk }, ...prev.slice(idx + 1)];
    });
  }

  function finishStreamEntry(r: GameResponse) {
    const id = streamEntryId.current;
    streamEntryId.current = null;
    setLog((prev) => {
      const idx = id === null ? -1 : prev.findIndex((e) => e.id === id);
      if (idx < 0) return prev; // nenhum chunk chegou — onTurn cuida
      const entry = prev[idx];
      return [
        ...prev.slice(0, idx),
        { ...entry, text: r.message, type: r.message_type || "STORY", streaming: false,
          visual: entry.visual ?? r.visual?.cue },
        ...prev.slice(idx + 1),
      ];
    });
    pendingVisual.current = null;
  }

  async function handleAction(text: string, options: ActionOptions = {}) {
    if (busy || !text.trim() || !gameId.current) return;
    const gid = gameId.current, generation = session.current, user = owner.current;
    const active = () => session.current === generation && gameId.current === gid;
    setBusy(true); setThinking(true);
    try {
      const old = loadPending(user, gid);
      if (old && old.payload.input_text !== text) throw new Error("Resolva a ação pendente antes de enviar outra.");
      const operation = await preparePending(user, gid, text, { ...options });
      setPending(operation);
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
      pushLog(operation.payload.input_text, "player", "STORY");
      setPhaseLabel(PHASE_TEXTS.campaign_manager);
      let hadChunks = false;
      try {
        const r = await api.sendActionStream(operation.payload.input_text, gid, {
          onPhase: node => { if (active()) setPhaseLabel(PHASE_TEXTS[node] ?? null); },
          onRoute: route => { if (active()) setPhaseLabel(ROUTE_TEXTS[route] ?? PHASE_TEXTS.storyteller); },
          onVisual: visual => { if (active()) attachStreamVisual(visual); },
          onChunk: (chunk, done) => {
            if (active()) {
              if (!done) hadChunks = true;
              appendChunk(chunk, done);
            }
          },
        }, requestOptions);
        clearPending(user, gid);
        if (!active()) return;
        setPending(null);
        if (hadChunks) { finishStreamEntry(r); setData(r); } else onTurn(r);
      } catch (error) {
        if (!active()) return;
        if (error instanceof api.HttpError && error.status < 500) {
          // A definitive validation failure can be edited; a conflict must be resolved.
          if ([400, 422].includes(error.status)) { clearPending(user, gid); setPending(null); }
          throw error;
        }
        const orphan = streamEntryId.current;
        streamEntryId.current = null; pendingVisual.current = null;
        if (orphan !== null) setLog(prev => prev.filter(e => e.id !== orphan));
        const r = await api.sendAction(operation.payload.input_text, gid, requestOptions);
        clearPending(user, gid);
        if (active()) { setPending(null); onTurn(r); }
      }
    } catch (error) {
      if (active()) setBanner({ msg: "Ação não confirmada: " + errMsg(error), kind: "error" });
    } finally {
      if (active()) { setThinking(false); setPhaseLabel(null); setBusy(false); }
    }
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
    if (session.current === generation) setLog([...entries.values()].map(entry => ({ ...entry, id: logSeq.current++ })));
  }

  function handleContinue() {
    if (continueData?.game_id) void handleContinueSave(continueData.game_id);
  }

  async function handleContinueSave(gid: string) {
    if (busy) return;
    const generation = ++session.current;
    setBusy(true);
    try {
      const r = await api.getState(gid);
      if (session.current !== generation) return;
      gameId.current = gid;
      localStorage.setItem(LS_KEY, gid);
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
      if (session.current === generation) setBanner({ msg: "Não consegui abrir a campanha: " + errMsg(err), kind: "error" });
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
        localStorage.removeItem(LS_KEY);
      }
      const list = await api.getSaves();
      setSaves(list);
      if (list.length === 0) setScreen("create");
    } catch (err) {
      setBanner({ msg: "Não consegui excluir: " + errMsg(err), kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  function handleNew() {
    if (busy) return;
    session.current++;
    setPending(null);
    setScreen(data?.combat_simulation?.enabled ? "simulator" : "create");
    setData(null);
  }

  const handleUiError = useCallback((message: string) => {
    setBanner({ msg: message, kind: "error" });
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
      setBanner({ msg: "Não deu para equipar: " + errMsg(err), kind: "error" });
    } finally {
      if (session.current === generation) setBusy(false);
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
      setBanner({ msg: "Escolha recusada: " + errMsg(err), kind: "error" });
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
      setBanner({ msg: "A Roda hesitou: " + errMsg(err), kind: "error" });
    } finally {
      if (session.current === generation) setBusy(false);
    }
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="atmosphere" aria-hidden />
      <EmberField />
      <Banner state={banner} onDone={() => setBanner(null)} />
      {screen === "play" && pending && <button className="pending-operation btn" disabled={busy}
        onClick={() => void handleAction(pending.payload.input_text)}>
        Consultar / retomar ação pendente
      </button>}
      {authRequired && screen !== "auth" && screen !== "play" && (
        <button className="session-logout btn btn--ghost" disabled={busy}
          onClick={() => void handleLogout()}>
          Encerrar sessão
        </button>
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
            <AuthScreen busy={busy} onLogin={handleLogin} error={authError} />
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
          <motion.div
            key="play"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          >
            <PlayScreen
              data={data}
              log={log}
              thinking={thinking}
              thinkingLabel={phaseLabel}
              busy={busy}
              onAction={handleAction}
              onNew={handleNew}
              onLevelUp={handleLevelUp}
              onEquip={handleEquip}
              onLogout={authRequired ? handleLogout : undefined}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </MotionConfig>
  );
}

function errMsg(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
