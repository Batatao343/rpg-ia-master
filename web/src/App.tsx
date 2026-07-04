import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import * as api from "./api";
import { looksDegraded } from "./lib";
import type { GameResponse, CreatePayload, LogEntry } from "./types";
import { Banner, type BannerState } from "./components/Banner";
import { CreateScreen } from "./components/CreateScreen";
import { PlayScreen } from "./components/PlayScreen";
import { EmberField } from "./components/EmberField";

const LS_KEY = "cronicas_game_id";

export function App() {
  const [screen, setScreen] = useState<"create" | "play">("create");
  const [data, setData] = useState<GameResponse | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [banner, setBanner] = useState<BannerState | null>(null);
  const [continueData, setContinueData] = useState<GameResponse | null>(null);

  const gameId = useRef<string | null>(localStorage.getItem(LS_KEY));
  const logSeq = useRef(0);
  const simNoticed = useRef(false);

  // Oferece retomar a última jornada salva, se houver.
  useEffect(() => {
    const saved = localStorage.getItem(LS_KEY);
    if (!saved) return;
    api
      .getState(saved)
      .then((r) => setContinueData(r))
      .catch(() => localStorage.removeItem(LS_KEY)); // save sumiu
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

  async function handleAction(text: string) {
    if (busy || !text.trim()) return;
    pushLog(text, "player", "STORY");
    setBusy(true);
    setThinking(true);
    try {
      const r = await api.sendAction(text, gameId.current);
      onTurn(r);
    } catch (err) {
      setBanner({ msg: "O destino tropeçou: " + errMsg(err), kind: "error" });
    } finally {
      setThinking(false);
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
        {screen === "create" ? (
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
