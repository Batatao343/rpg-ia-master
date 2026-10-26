import { useCallback, useEffect, useRef, useState } from "react";

/** Cadência constante (SPEC-320 R7): um tick a cada 30 ms, sem aleatoriedade. */
export const TYPEWRITER_TICK_MS = 30;
/** D1: teto de duração da revelação de um beat. */
export const TYPEWRITER_MAX_MS = 2500;
/** Com texto crescendo por chunks, o cursor nunca fica mais que ~1 s atrás do recebido. */
export const TYPEWRITER_LAG_MS = 1000;
/** Passo mínimo por tick (~150 car/s). */
export const TYPEWRITER_BASE_STEP = 5;

/** SPEC-235 R7: entries that do not animate (history) must render full text on frame 1.
 *  SPEC-320 R5: com efeitos desligados (reduced-motion / kill switch) também. */
export function typewriterInitial(text: string, enabled: boolean, effects: boolean = true): string {
  return enabled && effects ? "" : text;
}

/** Caracteres por tick para revelar `textLen` em no máximo `maxMs` (nunca abaixo do passo base). */
export function typewriterCharsPerTick(textLen: number, maxMs: number = TYPEWRITER_MAX_MS,
                                       tickMs: number = TYPEWRITER_TICK_MS): number {
  const ticks = Math.max(1, Math.floor(maxMs / tickMs));
  return Math.max(TYPEWRITER_BASE_STEP, Math.ceil(textLen / ticks));
}

/** One animation tick (determinístico); `done` when the whole text is revealed. */
export function typewriterStep(text: string, idx: number, charsPerTick: number = TYPEWRITER_BASE_STEP):
  { idx: number; done: boolean } {
  const next = idx + Math.max(1, Math.floor(charsPerTick));
  return { idx: next, done: next >= text.length };
}

/**
 * SPEC-319 R7: o que fazer quando o texto muda. `follow` = tokens reais chegando (a entrada vem
 * de deltas do servidor): o cursor ACOMPANHA o recebido, sem atraso artificial. `clear` = `reset`
 * do servidor (fallback de provider no meio do stream): descarta o parcial. `jump` = `replace`
 * (texto final não é extensão do exibido). `animate` = pseudo-streaming da SPEC-316.
 */
export type TypewriterPlan = "clear" | "jump" | "follow" | "animate";
export function typewriterPlan(prev: string, text: string, follow: boolean): TypewriterPlan {
  if (!text) return "clear";
  if (prev && !text.startsWith(prev)) return "jump";
  return follow ? "follow" : "animate";
}

export interface TypewriterOpts { maxMs?: number; effects?: boolean; follow?: boolean }

/**
 * Hook para revelar texto progressivamente (efeito typewriter).
 * `onDone` dispara (uma vez por revelação) quando a animação termina ou é pulada via `reveal()`.
 */
export function useTypewriter(text: string, enabled: boolean = true, onDone?: () => void, opts: TypewriterOpts = {}) {
  const { maxMs = TYPEWRITER_MAX_MS, effects = true, follow = false } = opts;
  const [displayedText, setDisplayedText] = useState(() => typewriterInitial(text, enabled, effects));
  const [revealing, setRevealing] = useState(false);
  // Texto já exibido, em ref: o React não garante rodar updaters de forma síncrona (P2-1).
  const shownRef = useRef(typewriterInitial(text, enabled, effects));
  const doneRef = useRef(onDone);
  const revealRef = useRef<(() => void) | null>(null);
  useEffect(() => { doneRef.current = onDone; });

  useEffect(() => {
    if (!enabled || !text || !effects) {
      shownRef.current = text;
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
      setDisplayedText(text);
      setRevealing(false);
      revealRef.current = null;
      if (enabled) doneRef.current?.();
      return;
    }

    // spec streaming-turno-sse: texto pode CRESCER (chunks SSE) — continua de
    // onde parou em vez de recomeçar do zero a cada chunk.
    const prev = shownRef.current;
    if (typewriterPlan(prev, text, follow) === "follow") {
      // SPEC-319 R7: tokens reais — mostra o que chegou agora; o fim (`done`) apenas desliga `enabled`.
      shownRef.current = text;
      setDisplayedText(text);
      setRevealing(false);
      revealRef.current = null;
      return;
    }
    if (prev && !text.startsWith(prev)) {
      // P2-9: `replace` (texto final diferente) não é prefixo do já exibido: revela direto, sem redigitar.
      shownRef.current = text;
      setDisplayedText(text);
      setRevealing(false);
      revealRef.current = null;
      doneRef.current?.();
      return;
    }
    let idx = prev.length;
    // Teto de duração: no 1º trecho usa maxMs; ao continuar texto crescente, o atraso máximo é ~1 s.
    const perTick = typewriterCharsPerTick(text.length - idx, idx > 0 ? Math.min(maxMs, TYPEWRITER_LAG_MS) : maxMs);
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      clearInterval(interval);
      shownRef.current = text;
      setDisplayedText(text);
      setRevealing(false);
      revealRef.current = null;
      doneRef.current?.();
    };
    const interval = setInterval(() => {
      const step = typewriterStep(text, idx, perTick);
      idx = step.idx;
      if (step.done) finish();
      else { shownRef.current = text.slice(0, idx); setDisplayedText(shownRef.current); }
    }, TYPEWRITER_TICK_MS);
    revealRef.current = finish;
    setRevealing(true);

    return () => { finished = true; clearInterval(interval); revealRef.current = null; };
  }, [text, enabled, effects, maxMs, follow]);

  /** Revela tudo agora (toque/clique/Esc/Espaço). */
  const reveal = useCallback(() => revealRef.current?.(), []);

  return { displayedText, reveal, revealing };
}
