import { useEffect, useState } from "react";

/**
 * Hook para revelar texto progressivamente (efeito typewriter).
 * Completa quase instantaneamente (30ms por 50 chars) para parecer natural.
 */
export function useTypewriter(text: string, enabled: boolean = true) {
  const [displayedText, setDisplayedText] = useState("");

  useEffect(() => {
    if (!enabled || !text) {
      setDisplayedText(text);
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
      idx += 1 + Math.floor(Math.random() * 8);  // 1-8 chars por frame
      if (idx >= text.length) {
        setDisplayedText(text);
        clearInterval(interval);
      } else {
        setDisplayedText(text.slice(0, idx));
      }
    }, 30);

    return () => clearInterval(interval);
  }, [text, enabled]);

  return displayedText;
}
