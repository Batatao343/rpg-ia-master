import { useEffect, type RefObject } from "react";

/** SPEC-321 R9: publica a altura medida do compositor em `--composer-h` (`:root`) para ancorar toasts e a
 *  barra de ação pendente ACIMA dele. `display: none` (superfície fora do chat) mede 0. */
export function useComposerHeight(ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const root = document.documentElement;
    const publish = () => root.style.setProperty("--composer-h", `${Math.ceil(node.getBoundingClientRect().height)}px`);
    publish();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", publish);
      return () => { window.removeEventListener("resize", publish); root.style.removeProperty("--composer-h"); };
    }
    const observer = new ResizeObserver(publish);
    observer.observe(node);
    return () => { observer.disconnect(); root.style.removeProperty("--composer-h"); };
  }, [ref]);
}
