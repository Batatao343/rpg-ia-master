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

    let idx = 0;
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
