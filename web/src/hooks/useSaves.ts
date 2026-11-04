import * as api from "../api";
import { safeStorage } from "../safeStorage";
import { loadPending, clearPending } from "../pendingOperation";
import { resetBookScroll } from "../workspace/chatSessionStore";
import { speakerFromHistory } from "../lib";
import { errMsg, errRequestId } from "../lib/errorMessages";
import type { CombatSimulatorPayload, CreatePayload, GameResponse } from "../types";
import { LS_KEY, type AppCore } from "./core";

/** Carrega o histórico paginado do save para o log. Sem estado próprio: só lê/escreve no `core`. */
export async function loadHistory(core: AppCore, gid: string, generation: number) {
  const { session, logSeq, setBanner, setLog } = core;
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

/** Criar/continuar/excluir/nova jornada (SPEC-383 R1 item 2). Movido de `App.tsx` sem mudar corpo. */
export function useSaves(
  core: AppCore,
  deps: {
    onTurn: (r: GameResponse) => number;
    openImageQuote: (id: string, type?: api.ImageQuote["type"], reformulation?: boolean, offerId?: string) => Promise<void>;
    resetImageQuote: () => void;
    resetTurn: () => void;
    loadHistory: (gid: string, generation: number) => Promise<void>;
  },
) {
  const { busy, setBusy, session, owner, gameId, data, setData, continueData, setScreen, setLog, setThinking,
    setBanner, setPending, setSaves } = core;
  const { onTurn, openImageQuote, resetImageQuote, resetTurn, loadHistory } = deps;

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
      // SPEC-347 R11.2: a memória de rolagem serve à troca de superfície, não a reabrir o save — o Livro abre no fim.
      resetBookScroll(gid);
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

  return { handleCreate, handleCreateSimulation, handleContinue, handleContinueSave, handleDeleteSave, handleNew };
}
