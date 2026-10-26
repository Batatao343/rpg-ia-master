import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** SPEC-204 R16 / SPEC-201 A09 (M26): foco inicial dentro do diálogo, Tab preso
 *  nele, Esc opcional e devolução do foco ao elemento de origem ao fechar. */
export function useModalFocus(ref: RefObject<HTMLElement | null>, onEscape?: () => void) {
  const escape = useRef(onEscape);
  useEffect(() => { escape.current = onEscape; });
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusables = () => Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE))
      .filter((el) => !el.closest("[hidden]"));
    (focusables()[0] ?? node).focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && escape.current) {
        event.preventDefault();
        escape.current();
        return;
      }
      if (event.key !== "Tab") return;
      const list = focusables();
      if (!list.length) { event.preventDefault(); node.focus(); return; }
      const first = list[0];
      const last = list[list.length - 1];
      const current = document.activeElement;
      if (!node.contains(current)) { event.preventDefault(); first.focus(); }
      else if (event.shiftKey && current === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && current === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      const target = previous && previous.isConnected && previous !== document.body ? previous
        : document.querySelector<HTMLElement>('[aria-label="Sua ação"]');
      target?.focus();
    };
  }, [ref]);
}
