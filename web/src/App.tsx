import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import * as api from "./api";
import { looksDegraded } from "./lib";
import type { GameResponse, CreatePayload, LogEntry, SaveSummary } from "./types";
import { Banner, type BannerState } from "./components/Banner";
import { CreateScreen } from "./components/CreateScreen";
import { PlayScreen } from "./components/PlayScreen";
import { SaveScreen } from "./components/SaveScreen";
import { EmberField } from "./components/EmberField";

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
  const [screen, setScreen] = useState<"saves" | "create" | "play">("create");
  const [data, setData] = useState<GameResponse | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [phaseLabel, setPhaseLabel] = useState<string | null>(null);
  const [banner, setBanner] = useState<BannerState | null>(null);
  const [continueData, setContinueData] = useState<GameResponse | null>(null);
  const [saves, setSaves] = useState<SaveSummary[]>([]);

  const gameId = useRef<string | null>(localStorage.getItem(LS_KEY));
  const logSeq = useRef(0);
  const simNoticed = useRef(false);

  // spec polish-sessao (R3): havendo campanhas salvas, a tela inicial as lista.
  useEffect(() => {
    api
      .getSaves()
      .then((list) => {
        setSaves(list);
        if (list.length > 0) setScreen("saves");
      })
      .catch(() => {
        // API antiga/sem saves — mantém o fluxo clássico de "continuar última"
        const saved = localStorage.getItem(LS_KEY);
        if (!saved) return;
        api
          .getState(saved)
          .then((r) => setContinueData(r))
          .catch(() => localStorage.removeItem(LS_KEY));
      });
  }, []);

  function pushLog(text: string, role: "player" | "narrator", type: LogEntry["type"]) {
    setLog((prev) => [...prev, { id: logSeq.current++, text, role, type }]);
  }

  function onTurn(r: GameResponse) {
    gameId.current = r.game_id || gameId.current;
    if (gameId.current) localStorage.setItem(LS_KEY, gameId.current);

    // Cria entrada com streaming=true, que ativa efeito typewriter
    setLog((prev) => [
      ...prev,
      { id: logSeq.current++, text: r.message, role: "narrator", type: r.message_type || "STORY", streaming: true }
    ]);

    // Após animação estar completa (300ms), finaliza a entrada
    setTimeout(() => {
      setLog((prev) => {
        if (prev.length === 0) return prev;
        const last = prev[prev.length - 1];
        return [...prev.slice(0, -1), { ...last, streaming: false }];
      });
    }, 300);

    setData(r);
    if (r.simulated && !simNoticed.current) {
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
    setScreen("play");
    setLog([]);
    setThinking(true);
    try {
      const r = await api.newGame(payload);
      onTurn(r);
    } catch (err) {
      setScreen("create");
      setBanner({ msg: "Falha ao criar personagem: " + errMsg(err), kind: "error" });
    } finally {
      setThinking(false);
      setBusy(false);
    }
  }

  // spec streaming-turno-sse (R4): chunks do servidor alimentam UMA entrada
  // "streaming" do log; o typewriter revela o texto conforme ele cresce.
  const streamEntryId = useRef<number | null>(null);

  function appendChunk(chunk: string, done: boolean) {
    if (done) return;
    setLog((prev) => {
      const id = streamEntryId.current;
      const idx = id === null ? -1 : prev.findIndex((e) => e.id === id);
      if (idx < 0) {
        const nid = logSeq.current++;
        streamEntryId.current = nid;
        return [...prev, { id: nid, text: chunk, role: "narrator" as const, type: "STORY" as const, streaming: true }];
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
        { ...entry, text: r.message, type: r.message_type || "STORY", streaming: false },
        ...prev.slice(idx + 1),
      ];
    });
  }

  async function handleAction(text: string) {
    if (busy || !text.trim()) return;
    pushLog(text, "player", "STORY");
    setBusy(true);
    setThinking(true);
    setPhaseLabel(PHASE_TEXTS.campaign_manager);
    try {
      let hadChunks = false;
      try {
        const r = await api.sendActionStream(text, gameId.current, {
          onPhase: (node) => setPhaseLabel(PHASE_TEXTS[node] ?? null),
          onRoute: (route) => setPhaseLabel(ROUTE_TEXTS[route] ?? PHASE_TEXTS.storyteller),
          onChunk: (chunk, done) => {
            hadChunks = true;
            appendChunk(chunk, done);
          },
        });
        gameId.current = r.game_id || gameId.current;
        if (gameId.current) localStorage.setItem(LS_KEY, gameId.current);
        if (hadChunks) {
          finishStreamEntry(r);
          setData(r);
        } else {
          onTurn(r);
        }
      } catch {
        // R4: fallback AUTOMÁTICO e silencioso pro POST clássico
        const orphan = streamEntryId.current;
        streamEntryId.current = null;
        if (orphan !== null) setLog((prev) => prev.filter((e) => e.id !== orphan));
        const r = await api.sendAction(text, gameId.current);
        onTurn(r);
      }
    } catch (err) {
      setBanner({ msg: "O destino tropeçou: " + errMsg(err), kind: "error" });
    } finally {
      setThinking(false);
      setPhaseLabel(null);
      setBusy(false);
    }
  }

  function handleContinue() {
    if (!continueData) return;
    gameId.current = continueData.game_id || gameId.current;
    setScreen("play");
    setLog([]);
    pushLog(continueData.message || "Você retoma sua jornada.", "narrator", continueData.message_type || "STORY");
    setData(continueData);
  }

  // spec polish-sessao (R3): continuar/excluir campanhas pela tela de saves.
  async function handleContinueSave(gid: string) {
    if (busy) return;
    setBusy(true);
    try {
      const r = await api.getState(gid);
      gameId.current = gid;
      localStorage.setItem(LS_KEY, gid);
      setScreen("play");
      setLog([]);
      pushLog(r.message || "Você retoma sua jornada.", "narrator", r.message_type || "STORY");
      setData(r);
    } catch (err) {
      setBanner({ msg: "Não consegui abrir a campanha: " + errMsg(err), kind: "error" });
    } finally {
      setBusy(false);
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
    setScreen("create");
    setData(null);
  }

  // Fase 4.3: equipar/desequipar e recarregar o estado completo (AC/ataque derivam).
  async function handleEquip(pick: { item_id?: string; unequip_slot?: string }) {
    if (busy || !gameId.current) return;
    setBusy(true);
    try {
      await api.postEquip({ ...pick, game_id: gameId.current });
      const r = await api.getState(gameId.current);
      setData(r);
    } catch (err) {
      setBanner({ msg: "Não deu para equipar: " + errMsg(err), kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  // Fase 4.1: aplica escolha de level up e mescla o player atualizado no estado.
  async function handleLevelUp(choiceId: string, pick: { ability_id?: string; attr?: string }) {
    if (busy) return;
    setBusy(true);
    try {
      const r = await api.postLevelUp({ choice_id: choiceId, ...pick, game_id: gameId.current });
      setData((prev) =>
        prev ? { ...prev, player_stats: { ...prev.player_stats, ...r.player_stats } } : prev
      );
    } catch (err) {
      setBanner({ msg: "Escolha recusada: " + errMsg(err), kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="atmosphere" aria-hidden />
      <EmberField />
      <Banner state={banner} onDone={() => setBanner(null)} />
      <AnimatePresence mode="wait">
        {screen === "saves" ? (
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
              onError={(m) => setBanner({ msg: m, kind: "error" })}
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
