import { useEffect, useRef, useState } from "react";

/** SPEC-235 R7: entries that do not animate (history) must render full text on frame 1. */
export function typewriterInitial(text: string, enabled: boolean): string {
  return enabled ? "" : text;
}

/** One animation tick: advance by 1-8 chars; `done` when the whole text is revealed. */
export function typewriterStep(text: string, idx: number, rand: number = Math.random()):
  { idx: number; done: boolean } {
  const next = idx + 1 + Math.floor(rand * 8);
  return { idx: next, done: next >= text.length };
}

/**
 * Hook para revelar texto progressivamente (efeito typewriter).
 * `onDone` dispara quando a animação termina (substitui timers fixos).
 */
export function useTypewriter(text: string, enabled: boolean = true, onDone?: () => void) {
  const [displayedText, setDisplayedText] = useState(() => typewriterInitial(text, enabled));
  const doneRef = useRef(onDone);
  useEffect(() => { doneRef.current = onDone; });

  useEffect(() => {
    if (!enabled || !text) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
      setDisplayedText(text);
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
    const interval = setInterval(() => {
      const step = typewriterStep(text, idx);
      idx = step.idx;
      if (step.done) {
        setDisplayedText(text);
        clearInterval(interval);
        doneRef.current?.();
      } else {
        setDisplayedText(text.slice(0, idx));
      }
    }, 30);

    return () => clearInterval(interval);
  }, [text, enabled]);

  return displayedText;
}
