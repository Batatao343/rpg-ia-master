import { useEffect, useState } from "react";

const KEYBOARD_DELTA_PX = 150;

/** SPEC-216 R4: no mobile a altura do app segue a viewport VISUAL (teclado virtual).
 *  Sem `visualViewport` cai para `innerHeight`; o CSS ainda tem `100dvh` como base.
 *  Devolve `keyboardOpen` (a viewport visual encolheu bastante em relacao a maior altura vista). */
export function useVisualViewport(enabled: boolean): boolean {
  const [keyboardOpen, setKeyboardOpen] = useState(false);
  useEffect(() => {
    const root = document.documentElement;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sincroniza estado com sistema externo (fetch/timer/DOM/assinatura) ao montar/trocar a chave; derivar em render mudaria o fluxo de carregamento
    if (!enabled) { root.style.removeProperty("--app-vh"); setKeyboardOpen(false); return; }
    const vv = window.visualViewport;
    let baseline = 0;
    let lastWidth = 0;
    const update = () => {
      const height = vv ? vv.height : window.innerHeight;
      const width = vv ? vv.width : window.innerWidth;
      if (width !== lastWidth) { baseline = 0; lastWidth = width; } // girou a tela
      baseline = Math.max(baseline, height);
      root.style.setProperty("--app-vh", `${Math.round(height)}px`);
      // So a altura decide: tocar em "Agir" tira o foco do campo antes de a viewport voltar,
      // e a barra nao pode reaparecer no meio do toque (deslocaria o botao).
      setKeyboardOpen(baseline - height > KEYBOARD_DELTA_PX);
    };
    update();
    vv?.addEventListener("resize", update);
    window.addEventListener("resize", update);
    return () => {
      vv?.removeEventListener("resize", update);
      window.removeEventListener("resize", update);
      root.style.removeProperty("--app-vh");
    };
  }, [enabled]);
  return keyboardOpen;
}
