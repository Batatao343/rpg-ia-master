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

export interface TypewriterOpts { maxMs?: number; effects?: boolean }

/**
 * Hook para revelar texto progressivamente (efeito typewriter).
 * `onDone` dispara (uma vez por revelação) quando a animação termina ou é pulada via `reveal()`.
 */
export function useTypewriter(text: string, enabled: boolean = true, onDone?: () => void, opts: TypewriterOpts = {}) {
  const { maxMs = TYPEWRITER_MAX_MS, effects = true } = opts;
  const [displayedText, setDisplayedText] = useState(() => typewriterInitial(text, enabled, effects));
  const [revealing, setRevealing] = useState(false);
  const doneRef = useRef(onDone);
  const revealRef = useRef<(() => void) | null>(null);
  useEffect(() => { doneRef.current = onDone; });

  useEffect(() => {
    if (!enabled || !text || !effects) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
      setDisplayedText(text);
      setRevealing(false);
      revealRef.current = null;
      if (enabled) doneRef.current?.();
      return;
    }

    // spec streaming-turno-sse: texto pode CRESCER (chunks SSE) — continua de
    // onde parou em vez de recomeçar do zero a cada chunk.
    let idx = 0;
    setDisplayedText((prev) => {
      idx = text.startsWith(prev) ? prev.length : 0;
      return prev;
    });
    // Teto de duração: no 1º trecho usa maxMs; ao continuar texto crescente, o atraso máximo é ~1 s.
    const perTick = typewriterCharsPerTick(text.length - idx, idx > 0 ? Math.min(maxMs, TYPEWRITER_LAG_MS) : maxMs);
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      clearInterval(interval);
      setDisplayedText(text);
      setRevealing(false);
      revealRef.current = null;
      doneRef.current?.();
    };
    const interval = setInterval(() => {
      const step = typewriterStep(text, idx, perTick);
      idx = step.idx;
      if (step.done) finish();
      else setDisplayedText(text.slice(0, idx));
    }, TYPEWRITER_TICK_MS);
    revealRef.current = finish;
    setRevealing(true);

    return () => { finished = true; clearInterval(interval); revealRef.current = null; };
  }, [text, enabled, effects, maxMs]);

  /** Revela tudo agora (toque/clique/Esc/Espaço). */
  const reveal = useCallback(() => revealRef.current?.(), []);

  return { displayedText, reveal, revealing };
}
