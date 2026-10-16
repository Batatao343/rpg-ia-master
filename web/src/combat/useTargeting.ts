import { useCallback, useEffect, useReducer, useRef } from "react";
import { IDLE, targetingReducer, type AimSource, type TargetingState } from "./targeting";

/** SPEC-205: máquina idle → aiming → submitting → idle. Só estado efêmero de UI
 *  (nenhum número de jogo): Esc / clique fora cancelam; `busy` trava a mira. */
export function useTargeting(busy: boolean, resetKey: unknown) {
  const [state, dispatch] = useReducer(targetingReducer, IDLE as TargetingState);
  const lock = useRef(false);
  const sawBusy = useRef(false);

  // Libera o gesto na borda de descida do `busy` (resposta do servidor chegou).
  useEffect(() => {
    if (state.phase !== "submitting") { sawBusy.current = false; return; }
    if (busy) { sawBusy.current = true; return; }
    if (sawBusy.current) { lock.current = false; dispatch({ type: "release" }); return; }
    // onAction recusou sem ocupar o turno (ex.: ação pendente): não deixa o gesto preso.
    const timer = setTimeout(() => {
      if (!sawBusy.current) { lock.current = false; dispatch({ type: "release" }); }
    }, 1500);
    return () => clearTimeout(timer);
  }, [busy, state.phase]);

  // Combate mudou de rodada/estado: descarta qualquer mira antiga.
  useEffect(() => { if (state.phase === "aiming") dispatch({ type: "cancel" }); },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [resetKey]);

  useEffect(() => {
    if (state.phase !== "aiming") return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { event.stopPropagation(); dispatch({ type: "cancel" }); } };
    const onPointer = (event: PointerEvent) => {
      const el = event.target as Element | null;
      if (!el?.closest("[data-aim-safe]")) dispatch({ type: "cancel" });
    };
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("pointerdown", onPointer, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("pointerdown", onPointer, true);
    };
  }, [state.phase]);

  const aim = useCallback((source: AimSource) => { if (!lock.current) dispatch({ type: "aim", source }); }, []);
  const cancel = useCallback(() => dispatch({ type: "cancel" }), []);
  /** Trava contra duplo clique/Enter repetido; devolve false se já enviado. */
  const begin = useCallback((): boolean => {
    if (lock.current) return false;
    lock.current = true;
    dispatch({ type: "submit" });
    return true;
  }, []);
  /** Gesto direto (sem mira): também trava até a resposta. */
  const beginDirect = useCallback((): boolean => {
    if (lock.current) return false;
    lock.current = true;
    dispatch({ type: "aim", source: { kind: "basic", key: "__direct" } });
    dispatch({ type: "submit" });
    return true;
  }, []);
  /** Libera sem esperar `busy` (ex.: onAction recusou antes de enviar). */
  const abort = useCallback(() => { lock.current = false; dispatch({ type: "release" }); }, []);

  return { state, aim, cancel, begin, beginDirect, abort };
}
