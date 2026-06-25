import { useEffect, useRef, useState } from "react";
import * as api from "./api";
import { looksDegraded } from "./lib";
import type { GameResponse, CreatePayload, LogEntry } from "./types";
import { Banner, type BannerState } from "./components/Banner";
import { CreateScreen } from "./components/CreateScreen";
import { PlayScreen } from "./components/PlayScreen";

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
    pushLog(r.message, "narrator", r.message_type || "STORY");
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

  return (
    <>
      <Banner state={banner} onDone={() => setBanner(null)} />
      {screen === "create" ? (
        <CreateScreen
          busy={busy}
          continueData={continueData}
          onCreate={handleCreate}
          onContinue={handleContinue}
          onError={(m) => setBanner({ msg: m, kind: "error" })}
        />
      ) : (
        <PlayScreen
          data={data}
          log={log}
          thinking={thinking}
          busy={busy}
          onAction={handleAction}
          onNew={handleNew}
        />
      )}
    </>
  );
}

function errMsg(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
